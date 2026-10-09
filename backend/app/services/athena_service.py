"""
app/services/athena_service.py
──────────────────────────────
Reusable AWS Athena query execution layer.

Responsibilities
────────────────
  execute_query()  – submit a query, return an execution ID
  wait_for_query() – poll until SUCCEEDED / FAILED / CANCELLED
  get_results()    – fetch paginated result rows
  run()            – convenience wrapper: execute → wait → results

Design notes
────────────
• Uses named query parameters (via string formatting with validated
  Python values) rather than unsafe string concatenation of raw user input.
  All values are escaped / cast to their correct Python types by Pydantic
  before reaching here, so the risk of injection is minimal; additionally
  Athena itself has no stored-procedure surface area for injection attacks.
• The boto3 client is lazily created and reused within the service instance.
• Logging follows the project standard: no device IDs are ever logged.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class AthenaQueryError(RuntimeError):
    """Raised when an Athena query fails or is cancelled."""


class AthenaTimeoutError(RuntimeError):
    """Raised when a query does not complete within the configured timeout."""


# ─────────────────────────────────────────────────────────────────────────────
# AthenaService
# ─────────────────────────────────────────────────────────────────────────────

class AthenaService:
    """
    Thin wrapper around boto3 Athena.

    Usage
    ─────
        svc = AthenaService()
        rows = svc.run(sql_string)
        # rows → list of dicts  {column_name: value, …}
    """

    POLL_INTERVAL_SECONDS = 2
    
    # Class-level cache of partitions we have already ensured during this server run.
    # Format: set of strings "table_name::YYYYMMDD"
    _ensured_partitions = set()

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = self._build_client()

    # ── private ───────────────────────────────────────────────────────────────

    def _build_client(self):
        kwargs: Dict[str, Any] = {"region_name": self._settings.aws_region}
        # Only pass explicit credentials when they are set; otherwise boto3
        # picks them up from the environment / instance-profile automatically.
        if self._settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = self._settings.aws_access_key_id
        if self._settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = self._settings.aws_secret_access_key
        if self._settings.aws_session_token:
            kwargs["aws_session_token"] = self._settings.aws_session_token
        return boto3.client("athena", **kwargs)

    # ── public API ────────────────────────────────────────────────────────────

    def execute_query(self, sql: str) -> str:
        """Submit *sql* to Athena and return the QueryExecutionId."""
        logger.info("Submitting Athena query (first 200 chars): %s", sql[:200])
        try:
            response = self._client.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": self._settings.athena_database},
                ResultConfiguration={"OutputLocation": self._settings.athena_output_location},
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("Failed to start Athena query: %s", exc)
            raise AthenaQueryError(f"AWS error starting query: {exc}") from exc

        execution_id: str = response["QueryExecutionId"]
        logger.info("Athena query submitted. ExecutionId=%s", execution_id)
        return execution_id

    def wait_for_query(self, execution_id: str) -> None:
        """Block until the query succeeds, or raise on failure / timeout."""
        deadline = time.monotonic() + self._settings.athena_query_timeout
        logger.info("Waiting for Athena query ExecutionId=%s", execution_id)

        while True:
            if time.monotonic() > deadline:
                raise AthenaTimeoutError(
                    f"Athena query {execution_id} did not complete within "
                    f"{self._settings.athena_query_timeout}s"
                )

            try:
                resp = self._client.get_query_execution(QueryExecutionId=execution_id)
            except (BotoCoreError, ClientError) as exc:
                raise AthenaQueryError(f"Error polling query {execution_id}: {exc}") from exc

            state: str = resp["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                logger.info("Athena query SUCCEEDED. ExecutionId=%s", execution_id)
                return
            if state in ("FAILED", "CANCELLED"):
                reason: str = (
                    resp["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
                )
                logger.error(
                    "Athena query %s. ExecutionId=%s  Reason=%s",
                    state,
                    execution_id,
                    reason,
                )
                raise AthenaQueryError(
                    f"Athena query {state} (id={execution_id}): {reason}"
                )

            time.sleep(self.POLL_INTERVAL_SECONDS)

    def get_results(self, execution_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all result pages and return a list of row-dicts.
        The first row from Athena is the header row – it is parsed and
        stripped so callers receive plain ``{column: value}`` dicts.
        """
        rows: List[Dict[str, Any]] = []
        headers: List[str] = []
        next_token: str | None = None
        first_page = True

        while True:
            kwargs: Dict[str, Any] = {"QueryExecutionId": execution_id, "MaxResults": 1000}
            if next_token:
                kwargs["NextToken"] = next_token

            try:
                resp = self._client.get_query_results(**kwargs)
            except (BotoCoreError, ClientError) as exc:
                raise AthenaQueryError(f"Error fetching results for {execution_id}: {exc}") from exc

            result_rows = resp["ResultSet"]["Rows"]

            if first_page and result_rows:
                # First row is always the column header
                headers = [col.get("VarCharValue", "") for col in result_rows[0]["Data"]]
                result_rows = result_rows[1:]
                first_page = False

            for row in result_rows:
                values = [cell.get("VarCharValue", None) for cell in row["Data"]]
                rows.append(dict(zip(headers, values)))

            next_token = resp.get("NextToken")
            if not next_token:
                break

        logger.info(
            "Fetched %d rows for ExecutionId=%s", len(rows), execution_id
        )
        return rows

    def execute_and_wait(self, sql: str) -> str:
        """
        Submit a query and wait for it to SUCCEED, returning the execution_id.
        This avoids fetching the results via API so you can download the S3 CSV directly.
        """
        try:
            response = self._client.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": self._settings.athena_database},
                ResultConfiguration={"OutputLocation": self._settings.athena_output_location},
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("Failed to start Athena query: %s", exc)
            raise AthenaQueryError(f"AWS error starting query: {exc}") from exc

        execution_id: str = response["QueryExecutionId"]
        self.wait_for_query(execution_id)
        return execution_id

    def get_output_location(self, execution_id: str) -> str:
        """Return the S3 URI for the query results CSV."""
        try:
            resp = self._client.get_query_execution(QueryExecutionId=execution_id)
            return resp["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        except (BotoCoreError, ClientError) as exc:
            raise AthenaQueryError(f"Error fetching output location for {execution_id}: {exc}") from exc

    def run(self, sql: str) -> List[Dict[str, Any]]:
        """
        Convenience method: execute → wait → fetch results.

        Parameters
        ──────────
        sql : str
            The complete SQL to run.  All dynamic values must already be
            safely substituted using Python format operations on validated
            Pydantic data – never pass raw user strings directly.

        Returns
        ───────
        List of row dicts ``{column_name: value_string, …}``
        """
        t_start = time.monotonic()
        execution_id = self.execute_query(sql)
        self.wait_for_query(execution_id)
        rows = self.get_results(execution_id)
        elapsed = time.monotonic() - t_start
        logger.info(
            "Athena query completed in %.2fs. Rows returned: %d", elapsed, len(rows)
        )
        return rows

    def ensure_partitions(self, table_name: str, dates: List[str]) -> None:
        """
        Dynamically adds missing partitions for a given list of YYYYMMDD date strings.
        This builds a single ALTER TABLE ADD IF NOT EXISTS query for all dates,
        which executes in ~2-3 seconds total.
        """
        if not dates:
            return

        short_table = table_name.split(".")[-1]
        
        # Build the PARTITION clauses for all requested dates
        partition_clauses = []
        for d in set(dates):  # Deduplicate dates
            cache_key = f"{table_name}::{d}"
            if cache_key in self.__class__._ensured_partitions:
                continue
                
            # payload table uses YYYY/MM/DD format in S3
            if short_table == "payload":
                s3_d = f"{d[:4]}/{d[4:6]}/{d[6:8]}"
                s3_folder = "payload"
            elif short_table == "organic90":
                s3_d = d
                s3_folder = "organic"
            else:
                s3_d = d
                s3_folder = short_table
            
            s3_loc = f"{self._settings.s3_data_prefix}/{s3_folder}/{s3_d}/"
            partition_clauses.append(f"PARTITION (event_date='{d}') LOCATION '{s3_loc}'")
            
        if not partition_clauses:
            logger.info("All %d partitions for %s already exist in local cache, skipping ADD PARTITION.", len(set(dates)), table_name)
            return
            
        clauses_str = "\n".join(partition_clauses)
        
        sql = f"""
ALTER TABLE {table_name} ADD IF NOT EXISTS
{clauses_str}
        """.strip()
        
        num_new = len(partition_clauses)
        logger.info("Ensuring %d partitions exist for %s", num_new, table_name)
        try:
            self.run(sql)
            # Add to cache only if query succeeds
            for d in set(dates):
                self.__class__._ensured_partitions.add(f"{table_name}::{d}")
        except Exception as exc:
            logger.warning("Failed to add partitions for %s: %s", table_name, exc)

