import logging
from app.services.training_data_service import TrainingDataService

logging.basicConfig(level=logging.INFO)
svc = TrainingDataService()
count = svc._count_rows("grofers", "train_final", "test_cache")
print("COUNT IS:", count)
