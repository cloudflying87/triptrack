from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.db import models
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
    LoanForm, PaymentForm, ManualPaymentForm, InvestmentForm, InvestmentTransactionForm,
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
    
    # Get loans user can view (family loans + shared + read-only)
    loans = Loan.objects.filter(
        models.Q(family=user_family, status='active') |  # Family loans
        models.Q(shared_with=request.user, status='active') |  # Shared with user
        models.Q(read_only_users=request.user, status='active')  # Read-only access
    ).select_related('loan_type').distinct()
    
    # Filter to only loans user can actually view
    viewable_loans = [loan for loan in loans if loan.can_view(request.user)]
    total_loan_balance = sum(loan.current_balance for loan in viewable_loans)
    
    # Get investments user can view
    investments = Investment.objects.filter(
        models.Q(family=user_family, status='active') |  # Family investments
        models.Q(shared_with=request.user, status='active') |  # Shared with user
        models.Q(read_only_users=request.user, status='active')  # Read-only access
    ).select_related('investment_type').distinct()
    
    # Filter to only investments user can actually view
    viewable_investments = [inv for inv in investments if inv.can_view(request.user)]
    total_investment_value = sum(inv.current_value for inv in viewable_investments)
    
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
        'loans': viewable_loans,
        'investments': viewable_investments,
        'total_loan_balance': total_loan_balance,
        'total_investment_value': total_investment_value,
        'net_worth': net_worth,
        'recent_payments': recent_payments,
        'recent_investments': recent_investments,
        'upcoming_payments': upcoming_payments,
        'loan_count': len(viewable_loans),
        'investment_count': len(viewable_investments),
        'today': date.today(),
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
            desired_payment = form.cleaned_data.get('desired_monthly_payment')
            
            # Calculate standard monthly payment
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
            
            # Calculate savings if desired payment is provided and higher
            if desired_payment and desired_payment > monthly_payment:
                from .utils import calculate_extra_payment_savings
                savings = calculate_extra_payment_savings(
                    principal=principal,
                    rate=rate,
                    current_payment=monthly_payment,
                    extra_payment=desired_payment - monthly_payment,
                    lump_sum=Decimal('0')
                )
                result['desired_payment'] = desired_payment
                result['savings'] = savings
            
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
    user_family = request.user.families.first()
    result = None
    existing_loan = None
    can_create_refinance = False
    
    # Check if a loan ID was passed in the URL
    loan_id = request.GET.get('loan')
    if loan_id and user_family:
        try:
            existing_loan = Loan.objects.get(id=loan_id, family=user_family, status='active')
        except Loan.DoesNotExist:
            existing_loan = None
    
    if request.method == 'POST':
        form = RefinanceCalculatorForm(request.POST, user_family=user_family)
        if form.is_valid():
            existing_loan = form.cleaned_data.get('existing_loan')
            
            # Get current loan details from existing loan or form
            if existing_loan:
                current_balance = existing_loan.current_balance
                current_rate = existing_loan.interest_rate
                current_remaining_months = existing_loan.get_remaining_payments()
                can_create_refinance = True
            else:
                current_balance = form.cleaned_data['current_balance']
                current_rate = form.cleaned_data['current_interest_rate']
                current_remaining_months = form.cleaned_data['current_remaining_months']
            
            result = calculate_refinance_comparison(
                current_balance=current_balance,
                current_rate=current_rate,
                current_remaining_months=current_remaining_months,
                new_rate=form.cleaned_data['new_interest_rate'],
                new_term_months=form.cleaned_data['new_term_months'],
                closing_costs=form.cleaned_data['closing_costs'],
                cash_out=form.cleaned_data.get('cash_out_amount', Decimal('0'))
            )
            
            # Add loan history information if existing loan selected
            if existing_loan:
                total_payments_made = existing_loan.payments.aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0.00')
                
                result['existing_loan'] = existing_loan
                result['total_payments_made'] = total_payments_made
                result['original_principal'] = existing_loan.principal_amount
                result['lifetime_savings'] = calculate_lifetime_savings(existing_loan, result)
    else:
        # Initialize form with existing loan if provided
        initial_data = {}
        if existing_loan:
            initial_data = {
                'existing_loan': existing_loan,
                'current_balance': existing_loan.current_balance,
                'current_interest_rate': existing_loan.interest_rate,
                'current_remaining_months': existing_loan.get_remaining_payments(),
            }
        form = RefinanceCalculatorForm(user_family=user_family, initial=initial_data)
    
    return render(request, 'loans/refinance_calculator.html', {
        'form': form,
        'result': result,
        'existing_loan': existing_loan,
        'can_create_refinance': can_create_refinance,
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
    """List all loans the user can view"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    # Get all loans user can view
    loans = Loan.objects.filter(
        models.Q(family=user_family) |  # Family loans
        models.Q(shared_with=request.user) |  # Shared with user
        models.Q(read_only_users=request.user)  # Read-only access
    ).select_related('loan_type').order_by('-created_at').distinct()
    
    # Filter to only loans user can actually view and add permission info
    viewable_loans = []
    for loan in loans:
        if loan.can_view(request.user):
            loan.user_can_edit = loan.can_edit(request.user)
            viewable_loans.append(loan)
    
    return render(request, 'loans/loan_list.html', {
        'loans': viewable_loans,
    })


@login_required
def loan_detail(request, loan_id):
    """Detailed view of a specific loan"""
    user_family = request.user.families.first()
    loan = get_object_or_404(Loan, id=loan_id)
    
    # Check if user can view this loan
    if not loan.can_view(request.user):
        messages.error(request, "You don't have permission to view this loan.")
        return redirect('loans:loan_list')
    
    # Get payments
    payments = loan.payments.order_by('-payment_date')
    
    # Get scheduled payments
    scheduled_payments = loan.scheduled_payments.order_by('payment_number')
    
    # Generate amortization schedule if none exists (only for automatic payment loans)
    if loan.payment_type == 'automatic' and not scheduled_payments.exists():
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
    
    # Calculate remaining payments and payoff date (only meaningful for automatic loans)
    if loan.payment_type == 'automatic':
        remaining_payments = loan.get_remaining_payments()
        if remaining_payments > 0:
            estimated_payoff = date.today() + relativedelta(months=remaining_payments)
        else:
            estimated_payoff = None
    else:
        remaining_payments = None
        estimated_payoff = None
    
    # For manual payment loans, calculate accrued interest
    accrued_interest = None
    next_payment_breakdown = None
    if loan.payment_type == 'manual':
        accrued_interest = loan.calculate_accrued_interest()
        next_payment_breakdown = loan.get_next_payment_breakdown()
    
    context = {
        'loan': loan,
        'payments': payments,
        'scheduled_payments': scheduled_payments,
        'remaining_payments': remaining_payments,
        'estimated_payoff': estimated_payoff,
        'total_paid': payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'total_interest_paid': payments.aggregate(total=Sum('interest_amount'))['total'] or Decimal('0.00'),
        'accrued_interest': accrued_interest,
        'next_payment_breakdown': next_payment_breakdown,
    }
    
    return render(request, 'loans/loan_detail.html', context)


@login_required
def investment_list(request):
    """List all investments the user can view"""
    user_family = request.user.families.first()
    
    if not user_family:
        messages.error(request, "Please join or create a family first.")
        return redirect('tracker:family_list')
    
    # Get all investments user can view
    investments = Investment.objects.filter(
        models.Q(family=user_family) |  # Family investments
        models.Q(shared_with=request.user) |  # Shared with user
        models.Q(read_only_users=request.user)  # Read-only access
    ).select_related('investment_type').order_by('-created_at').distinct()
    
    # Filter to only investments user can actually view and add permission info
    viewable_investments = []
    for investment in investments:
        if investment.can_view(request.user):
            investment.user_can_edit = investment.can_edit(request.user)
            viewable_investments.append(investment)
    
    return render(request, 'loans/investment_list.html', {
        'investments': viewable_investments,
    })


@login_required
def investment_detail(request, investment_id):
    """Detailed view of a specific investment"""
    user_family = request.user.families.first()
    investment = get_object_or_404(Investment, id=investment_id)
    
    # Check if user can view this investment
    if not investment.can_view(request.user):
        messages.error(request, "You don't have permission to view this investment.")
        return redirect('loans:investment_list')
    
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
            try:
                loan = form.save(commit=False)
                loan.family = user_family
                loan.created_by = request.user
                loan.current_balance = loan.principal_amount  # Set initial balance
                loan.save()
                
                messages.success(request, f"Loan '{loan.name}' added successfully!")
                return redirect('loans:loan_detail', loan_id=loan.id)
            except Exception as e:
                messages.error(request, f"Error saving loan: {str(e)}")
        else:
            # Debug: Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            if form.non_field_errors():
                for error in form.non_field_errors():
                    messages.error(request, f"Form error: {error}")
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
    loan = get_object_or_404(Loan, id=loan_id)
    
    # Check if user can edit this loan
    if not loan.can_edit(request.user):
        messages.error(request, "You don't have permission to add payments to this loan.")
        return redirect('loans:loan_detail', loan_id=loan.id)
    
    # Check for scheduled payment ID in URL parameters
    scheduled_payment_id = request.GET.get('scheduled_payment')
    scheduled_payment = None
    if scheduled_payment_id:
        try:
            scheduled_payment = ScheduledPayment.objects.get(
                id=scheduled_payment_id, 
                loan=loan, 
                is_paid=False
            )
        except ScheduledPayment.DoesNotExist:
            scheduled_payment = None
    
    # Use different forms based on payment type
    form_class = ManualPaymentForm if loan.payment_type == 'manual' else PaymentForm
    
    if request.method == 'POST':
        form = form_class(request.POST, loan=loan)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.loan = loan
            payment.created_by = request.user
            payment.save()
            
            # Mark scheduled payment as paid if this was from a scheduled payment
            if scheduled_payment and request.POST.get('mark_scheduled_paid') == 'true':
                scheduled_payment.is_paid = True
                scheduled_payment.actual_payment = payment
                scheduled_payment.save()
            
            # Show different success messages based on payment type
            if loan.payment_type == 'manual':
                breakdown = loan.get_next_payment_breakdown(payment.amount)
                if breakdown:
                    messages.success(request, 
                        f"Payment of ${payment.amount} recorded! "
                        f"Interest: ${payment.interest_amount:.2f}, "
                        f"Principal: ${payment.principal_amount:.2f}")
                else:
                    messages.success(request, f"Payment of ${payment.amount} recorded successfully!")
            else:
                success_msg = f"Payment of ${payment.amount} recorded successfully!"
                if scheduled_payment and request.POST.get('mark_scheduled_paid') == 'true':
                    success_msg += f" Scheduled payment for {scheduled_payment.due_date} marked as paid."
                messages.success(request, success_msg)
            
            return redirect('loans:loan_detail', loan_id=loan.id)
    else:
        # Pre-fill form with scheduled payment data if available
        initial_data = {}
        if scheduled_payment:
            initial_data = {
                'payment_date': scheduled_payment.due_date,
                'amount': scheduled_payment.scheduled_amount,
                'principal_amount': scheduled_payment.principal_amount,
                'interest_amount': scheduled_payment.interest_amount,
            }
        form = form_class(loan=loan, initial=initial_data)
    
    return render(request, 'loans/payment_form.html', {
        'form': form,
        'loan': loan,
        'title': f'Add Payment to {loan.name}',
        'is_manual_payment': loan.payment_type == 'manual',
        'scheduled_payment': scheduled_payment,
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
def create_refinance(request, loan_id):
    """Create a refinance record for an existing loan"""
    user_family = request.user.families.first()
    original_loan = get_object_or_404(Loan, id=loan_id, family=user_family)
    
    if request.method == 'POST':
        # Get refinance parameters from form or URL params
        new_rate = Decimal(request.POST.get('new_rate') or request.GET.get('new_rate'))
        new_term = int(request.POST.get('new_term') or request.GET.get('new_term'))
        closing_costs = Decimal(request.POST.get('closing_costs') or request.GET.get('closing_costs', '0'))
        cash_out = Decimal(request.POST.get('cash_out') or request.GET.get('cash_out', '0'))
        
        # Create the refinance record
        refinance = Refinance.objects.create(
            original_loan=original_loan,
            new_loan_amount=original_loan.current_balance + closing_costs + cash_out,
            new_interest_rate=new_rate,
            new_term_months=new_term,
            closing_costs=closing_costs,
            cash_out_amount=cash_out,
            refinance_date=date.today(),
            created_by=request.user
        )
        
        # Create the new loan record
        new_loan = Loan.objects.create(
            family=user_family,
            name=f"{original_loan.name} (Refinanced)",
            loan_type=original_loan.loan_type,
            lender=request.POST.get('new_lender', original_loan.lender),
            principal_amount=refinance.new_loan_amount,
            interest_rate=new_rate,
            term_months=new_term,
            start_date=refinance.refinance_date,
            first_payment_date=refinance.refinance_date + relativedelta(months=1),
            current_balance=refinance.new_loan_amount,
            status='active',
            created_by=request.user
        )
        
        # Update refinance with new loan reference
        refinance.new_loan = new_loan
        refinance.save()
        
        # Mark original loan as refinanced
        original_loan.status = 'refinanced'
        original_loan.save()
        
        messages.success(request, f"Refinance created successfully! New loan: {new_loan.name}")
        return redirect('loans:loan_detail', loan_id=new_loan.id)
    
    # GET request - show confirmation form
    new_rate = request.GET.get('new_rate')
    new_term = request.GET.get('new_term')
    closing_costs = request.GET.get('closing_costs', '0')
    cash_out = request.GET.get('cash_out', '0')
    
    if not new_rate or not new_term:
        messages.error(request, "Missing refinance parameters. Please use the refinance calculator first.")
        return redirect('loans:refinance_calculator')
    
    # Calculate the refinance comparison for display
    result = calculate_refinance_comparison(
        current_balance=original_loan.current_balance,
        current_rate=original_loan.interest_rate,
        current_remaining_months=original_loan.get_remaining_payments(),
        new_rate=Decimal(new_rate),
        new_term_months=int(new_term),
        closing_costs=Decimal(closing_costs),
        cash_out=Decimal(cash_out)
    )
    
    context = {
        'original_loan': original_loan,
        'new_rate': new_rate,
        'new_term': new_term,
        'closing_costs': closing_costs,
        'cash_out': cash_out,
        'result': result,
    }
    
    return render(request, 'loans/create_refinance.html', context)


@login_required
def offline_calculators(request):
    """Offline calculator page with client-side JavaScript"""
    return render(request, 'loans/offline_calculators.html')
