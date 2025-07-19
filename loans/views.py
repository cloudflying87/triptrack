from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import json
import csv
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from .models import (
    Loan, LoanType, Payment, ScheduledPayment, Refinance,
    Investment, InvestmentType, InvestmentTransaction
)
from .forms import (
    LoanForm, PaymentForm, InvestmentForm, InvestmentTransactionForm,
    LoanCalculatorForm, ExtraPaymentCalculatorForm, RefinanceCalculatorForm,
    InvestmentCalculatorForm
)
from .utils import (
    generate_amortization_schedule, calculate_extra_payment_savings,
    calculate_refinance_comparison, calculate_compound_interest,
    calculate_debt_avalanche, calculate_debt_snowball
)


@login_required
def dashboard(request):
    """Main dashboard showing all loans and investments"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.warning(request, "Please join or create a family to track loans and investments.")
        return redirect('tracker:family_list')
    
    # Get active loans
    loans = Loan.objects.filter(family=user_family, status='active').select_related('loan_type')
    total_loan_balance = loans.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
    
    # Get active investments
    investments = Investment.objects.filter(family=user_family, status='active').select_related('investment_type')
    total_investment_value = investments.aggregate(total=Sum('current_value'))['total'] or Decimal('0.00')
    
    # Calculate net worth (investments - loans)
    net_worth = total_investment_value - total_loan_balance
    
    # Recent transactions
    recent_payments = Payment.objects.filter(
        loan__family=user_family
    ).select_related('loan').order_by('-payment_date')[:5]
    
    recent_investments = InvestmentTransaction.objects.filter(
        investment__family=user_family
    ).select_related('investment').order_by('-transaction_date')[:5]
    
    # Upcoming payments (scheduled payments due in next 30 days)
    upcoming_payments = ScheduledPayment.objects.filter(
        loan__family=user_family,
        loan__status='active',
        is_paid=False,
        due_date__lte=date.today() + timedelta(days=30)
    ).select_related('loan').order_by('due_date')[:10]
    
    context = {
        'loans': loans,
        'investments': investments,
        'total_loan_balance': total_loan_balance,
        'total_investment_value': total_investment_value,
        'net_worth': net_worth,
        'recent_payments': recent_payments,
        'recent_investments': recent_investments,
        'upcoming_payments': upcoming_payments,
        'loan_count': loans.count(),
        'investment_count': investments.count(),
    }
    
    return render(request, 'loans/dashboard.html', context)


@login_required
def loan_calculator(request):
    """Basic loan calculator for monthly payments and total interest"""
    result = None
    amortization_schedule = None
    
    if request.method == 'POST':
        form = LoanCalculatorForm(request.POST)
        if form.is_valid():
            principal = form.cleaned_data['principal_amount']
            rate = form.cleaned_data['annual_interest_rate']
            term = form.cleaned_data['term_months']
            
            # Calculate monthly payment
            if rate == 0:
                monthly_payment = principal / term
            else:
                monthly_rate = rate / 100 / 12
                monthly_payment = (principal * monthly_rate * 
                                 (1 + monthly_rate) ** term) / \
                                 ((1 + monthly_rate) ** term - 1)
            
            total_payments = monthly_payment * term
            total_interest = total_payments - principal
            
            result = {
                'monthly_payment': round(monthly_payment, 2),
                'total_payments': round(total_payments, 2),
                'total_interest': round(total_interest, 2),
                'principal': principal,
                'rate': rate,
                'term': term,
            }
            
            # Generate amortization schedule if requested
            if form.cleaned_data.get('generate_schedule'):
                amortization_schedule = generate_amortization_schedule(
                    principal, rate, term, monthly_payment
                )
    else:
        form = LoanCalculatorForm()
    
    return render(request, 'loans/calculator.html', {
        'form': form,
        'result': result,
        'amortization_schedule': amortization_schedule,
    })


@login_required
def extra_payment_calculator(request):
    """Calculator for extra payments and interest savings"""
    result = None
    
    if request.method == 'POST':
        form = ExtraPaymentCalculatorForm(request.POST)
        if form.is_valid():
            result = calculate_extra_payment_savings(
                principal=form.cleaned_data['current_balance'],
                rate=form.cleaned_data['annual_interest_rate'],
                current_payment=form.cleaned_data['current_monthly_payment'],
                extra_payment=form.cleaned_data['extra_monthly_payment'],
                lump_sum=form.cleaned_data.get('lump_sum_payment', Decimal('0'))
            )
    else:
        form = ExtraPaymentCalculatorForm()
    
    return render(request, 'loans/extra_payment_calculator.html', {
        'form': form,
        'result': result,
    })


@login_required
def refinance_calculator(request):
    """Calculator for refinancing scenarios"""
    result = None
    
    if request.method == 'POST':
        form = RefinanceCalculatorForm(request.POST)
        if form.is_valid():
            result = calculate_refinance_comparison(
                current_balance=form.cleaned_data['current_balance'],
                current_rate=form.cleaned_data['current_interest_rate'],
                current_remaining_months=form.cleaned_data['current_remaining_months'],
                new_rate=form.cleaned_data['new_interest_rate'],
                new_term_months=form.cleaned_data['new_term_months'],
                closing_costs=form.cleaned_data['closing_costs'],
                cash_out=form.cleaned_data.get('cash_out_amount', Decimal('0'))
            )
    else:
        form = RefinanceCalculatorForm()
    
    return render(request, 'loans/refinance_calculator.html', {
        'form': form,
        'result': result,
    })


@login_required
def investment_calculator(request):
    """Compound interest calculator for investments"""
    result = None
    projections = None
    
    if request.method == 'POST':
        form = InvestmentCalculatorForm(request.POST)
        if form.is_valid():
            result = calculate_compound_interest(
                principal=form.cleaned_data['initial_amount'],
                rate=form.cleaned_data['annual_return_rate'],
                years=form.cleaned_data['investment_years'],
                monthly_contribution=form.cleaned_data.get('monthly_contribution', Decimal('0')),
                compounding=form.cleaned_data['compounding_frequency']
            )
            
            # Generate year-by-year projections
            projections = []
            for year in range(1, min(form.cleaned_data['investment_years'] + 1, 31)):
                year_result = calculate_compound_interest(
                    principal=form.cleaned_data['initial_amount'],
                    rate=form.cleaned_data['annual_return_rate'],
                    years=year,
                    monthly_contribution=form.cleaned_data.get('monthly_contribution', Decimal('0')),
                    compounding=form.cleaned_data['compounding_frequency']
                )
                projections.append({
                    'year': year,
                    'balance': year_result['future_value'],
                    'contributions': year_result['total_contributions'],
                    'interest': year_result['total_interest']
                })
    else:
        form = InvestmentCalculatorForm()
    
    return render(request, 'loans/investment_calculator.html', {
        'form': form,
        'result': result,
        'projections': projections,
    })


@login_required
def debt_payoff_strategies(request):
    """Compare debt avalanche vs snowball methods"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    loans = Loan.objects.filter(family=user_family, status='active').order_by('-interest_rate')
    
    avalanche_result = None
    snowball_result = None
    
    if loans.exists() and request.method == 'POST':
        extra_payment = Decimal(request.POST.get('extra_payment', '0'))
        
        if extra_payment > 0:
            avalanche_result = calculate_debt_avalanche(loans, extra_payment)
            snowball_result = calculate_debt_snowball(loans, extra_payment)
    
    return render(request, 'loans/debt_strategies.html', {
        'loans': loans,
        'avalanche_result': avalanche_result,
        'snowball_result': snowball_result,
    })


@login_required
def loan_list(request):
    """List all loans for the user's family"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    loans = Loan.objects.filter(family=user_family).select_related('loan_type').order_by('-created_at')
    
    return render(request, 'loans/loan_list.html', {
        'loans': loans,
    })


@login_required
def loan_detail(request, loan_id):
    """Detailed view of a specific loan"""
    user_family = request.user.families.first()
    loan = get_object_or_404(Loan, id=loan_id, family=user_family)
    
    # Get payments
    payments = loan.payments.order_by('-payment_date')
    
    # Get scheduled payments
    scheduled_payments = loan.scheduled_payments.order_by('payment_number')
    
    # Generate amortization schedule if none exists
    if not scheduled_payments.exists():
        schedule = generate_amortization_schedule(
            loan.principal_amount, 
            loan.interest_rate, 
            loan.term_months, 
            loan.monthly_payment
        )
        
        # Create scheduled payment records
        for payment_data in schedule:
            ScheduledPayment.objects.create(
                loan=loan,
                payment_number=payment_data['payment_number'],
                due_date=loan.first_payment_date + relativedelta(months=payment_data['payment_number']-1),
                scheduled_amount=payment_data['payment'],
                principal_amount=payment_data['principal'],
                interest_amount=payment_data['interest'],
                beginning_balance=payment_data['beginning_balance'],
                ending_balance=payment_data['ending_balance']
            )
        
        scheduled_payments = loan.scheduled_payments.order_by('payment_number')
    
    # Calculate remaining payments and payoff date
    remaining_payments = loan.get_remaining_payments()
    if remaining_payments > 0:
        estimated_payoff = date.today() + relativedelta(months=remaining_payments)
    else:
        estimated_payoff = None
    
    context = {
        'loan': loan,
        'payments': payments,
        'scheduled_payments': scheduled_payments,
        'remaining_payments': remaining_payments,
        'estimated_payoff': estimated_payoff,
        'total_paid': payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'total_interest_paid': payments.aggregate(total=Sum('interest_amount'))['total'] or Decimal('0.00'),
    }
    
    return render(request, 'loans/loan_detail.html', context)


@login_required
def investment_list(request):
    """List all investments for the user's family"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    investments = Investment.objects.filter(family=user_family).select_related('investment_type').order_by('-created_at')
    
    return render(request, 'loans/investment_list.html', {
        'investments': investments,
    })


@login_required
def investment_detail(request, investment_id):
    """Detailed view of a specific investment"""
    user_family = request.user.families.first()
    investment = get_object_or_404(Investment, id=investment_id, family=user_family)
    
    # Get transactions
    transactions = investment.transactions.order_by('-transaction_date')
    
    # Calculate performance metrics
    total_contributions = investment.get_total_contributions()
    total_return = investment.get_total_return()
    return_percentage = investment.get_return_percentage()
    
    # Calculate future projections
    projections = []
    for years in [1, 5, 10, 20, 30]:
        future_value = investment.calculate_future_value(years)
        projections.append({
            'years': years,
            'future_value': future_value,
        })
    
    context = {
        'investment': investment,
        'transactions': transactions,
        'total_contributions': total_contributions,
        'total_return': total_return,
        'return_percentage': return_percentage,
        'projections': projections,
    }
    
    return render(request, 'loans/investment_detail.html', context)


@login_required
def add_loan(request):
    """Add a new loan"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.family = user_family
            loan.created_by = request.user
            loan.current_balance = loan.principal_amount  # Set initial balance
            loan.save()
            
            messages.success(request, f"Loan '{loan.name}' added successfully!")
            return redirect('loans:loan_detail', loan_id=loan.id)
    else:
        form = LoanForm()
    
    return render(request, 'loans/loan_form.html', {
        'form': form,
        'title': 'Add New Loan',
    })


@login_required
def add_investment(request):
    """Add a new investment"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.family = user_family
            investment.created_by = request.user
            investment.current_value = investment.initial_amount  # Set initial value
            investment.save()
            
            messages.success(request, f"Investment '{investment.name}' added successfully!")
            return redirect('loans:investment_detail', investment_id=investment.id)
    else:
        form = InvestmentForm()
    
    return render(request, 'loans/investment_form.html', {
        'form': form,
        'title': 'Add New Investment',
    })


@login_required
def add_payment(request, loan_id):
    """Add a payment to a loan"""
    user_family = request.user.families.first()
    loan = get_object_or_404(Loan, id=loan_id, family=user_family)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, loan=loan)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.loan = loan
            payment.created_by = request.user
            payment.save()
            
            messages.success(request, f"Payment of ${payment.amount} recorded successfully!")
            return redirect('loans:loan_detail', loan_id=loan.id)
    else:
        form = PaymentForm(loan=loan)
    
    return render(request, 'loans/payment_form.html', {
        'form': form,
        'loan': loan,
        'title': f'Add Payment to {loan.name}',
    })


@login_required
def export_amortization_csv(request, loan_id):
    """Export amortization schedule as CSV"""
    user_family = request.user.families.first()
    loan = get_object_or_404(Loan, id=loan_id, family=user_family)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{loan.name}_amortization.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Payment #', 'Date', 'Payment', 'Principal', 'Interest', 'Balance'])
    
    scheduled_payments = loan.scheduled_payments.order_by('payment_number')
    for payment in scheduled_payments:
        writer.writerow([
            payment.payment_number,
            payment.due_date,
            f"{payment.scheduled_amount:.2f}",
            f"{payment.principal_amount:.2f}",
            f"{payment.interest_amount:.2f}",
            f"{payment.ending_balance:.2f}"
        ])
    
    return response


@login_required
def offline_calculators(request):
    """Offline calculator page with client-side JavaScript"""
    return render(request, 'loans/offline_calculators.html')
