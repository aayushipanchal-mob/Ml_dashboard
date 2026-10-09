from app.services.dashboard_service import DashboardService
svc = DashboardService()
print(svc._fetch_training_counts("com.grofers.customerapp"))
