from django.urls import path
from . import views

app_name = 'loans'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Calculators
    path('calculator/', views.loan_calculator, name='loan_calculator'),
    path('calculator/extra-payment/', views.extra_payment_calculator, name='extra_payment_calculator'),
    path('calculator/refinance/', views.refinance_calculator, name='refinance_calculator'),
    path('calculator/investment/', views.investment_calculator, name='investment_calculator'),
    path('calculator/offline/', views.offline_calculators, name='offline_calculators'),
    
    # Debt strategies
    path('debt-strategies/', views.debt_payoff_strategies, name='debt_strategies'),
    
    # Loans
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/<int:loan_id>/', views.loan_detail, name='loan_detail'),
    path('loans/add/', views.add_loan, name='add_loan'),
    path('loans/<int:loan_id>/payment/', views.add_payment, name='add_payment'),
    path('loans/<int:loan_id>/refinance/', views.create_refinance, name='create_refinance'),
    path('loans/<int:loan_id>/export-csv/', views.export_amortization_csv, name='export_amortization_csv'),
    
    # Investments
    path('investments/', views.investment_list, name='investment_list'),
    path('investments/<int:investment_id>/', views.investment_detail, name='investment_detail'),
    path('investments/add/', views.add_investment, name='add_investment'),
]