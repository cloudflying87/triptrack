from decimal import Decimal
import math
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def generate_amortization_schedule(principal, annual_rate, term_months, monthly_payment=None):
    """
    Generate complete amortization schedule for a loan
    
    Args:
        principal: Loan principal amount
        annual_rate: Annual interest rate (as percentage, e.g., 5.25)
        term_months: Loan term in months
        monthly_payment: Optional monthly payment amount
    
    Returns:
        List of dictionaries with payment details
    """
    if annual_rate == 0:
        monthly_payment = principal / term_months
        monthly_rate = 0
    else:
        monthly_rate = annual_rate / 100 / 12
        if monthly_payment is None:
            monthly_payment = (principal * monthly_rate * 
                             (1 + monthly_rate) ** term_months) / \
                             ((1 + monthly_rate) ** term_months - 1)
    
    schedule = []
    balance = principal
    
    for payment_num in range(1, term_months + 1):
        if monthly_rate == 0:
            interest_payment = 0
        else:
            interest_payment = balance * monthly_rate
        
        principal_payment = monthly_payment - interest_payment
        
        # Handle final payment
        if balance < principal_payment:
            principal_payment = balance
            monthly_payment = principal_payment + interest_payment
        
        balance -= principal_payment
        
        schedule.append({
            'payment_number': payment_num,
            'payment': round(monthly_payment, 2),
            'principal': round(principal_payment, 2),
            'interest': round(interest_payment, 2),
            'beginning_balance': round(balance + principal_payment, 2),
            'ending_balance': round(max(balance, 0), 2)
        })
        
        if balance <= 0:
            break
    
    return schedule


def calculate_extra_payment_savings(principal, rate, current_payment, extra_payment, lump_sum=0):
    """
    Calculate savings from extra payments
    
    Args:
        principal: Current loan balance
        rate: Annual interest rate (as percentage)
        current_payment: Current monthly payment
        extra_payment: Additional monthly payment
        lump_sum: One-time lump sum payment
    
    Returns:
        Dictionary with savings analysis
    """
    if rate == 0:
        monthly_rate = 0
    else:
        monthly_rate = rate / 100 / 12
    
    # Calculate standard payoff
    standard_months = calculate_remaining_months(principal, current_payment, monthly_rate)
    standard_total = current_payment * standard_months
    standard_interest = standard_total - principal
    
    # Apply lump sum if provided
    remaining_balance = principal - lump_sum
    if remaining_balance <= 0:
        return {
            'standard_months': standard_months,
            'standard_total_payments': standard_total,
            'standard_total_interest': standard_interest,
            'extra_months': 0,
            'extra_total_payments': lump_sum,
            'extra_total_interest': 0,
            'time_saved_months': standard_months,
            'interest_saved': standard_interest,
            'total_extra_payments': lump_sum
        }
    
    # Calculate with extra payments
    new_payment = current_payment + extra_payment
    extra_months = calculate_remaining_months(remaining_balance, new_payment, monthly_rate)
    extra_total = lump_sum + (new_payment * extra_months)
    extra_interest = extra_total - principal
    
    return {
        'standard_months': standard_months,
        'standard_total_payments': round(standard_total, 2),
        'standard_total_interest': round(standard_interest, 2),
        'extra_months': extra_months,
        'extra_total_payments': round(extra_total, 2),
        'extra_total_interest': round(extra_interest, 2),
        'time_saved_months': standard_months - extra_months,
        'interest_saved': round(standard_interest - extra_interest, 2),
        'total_extra_payments': round(lump_sum + (extra_payment * extra_months), 2)
    }


def calculate_remaining_months(balance, payment, monthly_rate):
    """Calculate remaining months to pay off a loan"""
    if monthly_rate == 0:
        return int(math.ceil(balance / payment))
    
    if payment <= balance * monthly_rate:
        return float('inf')  # Payment doesn't cover interest
    
    months = math.log(1 + (balance * monthly_rate) / payment) / math.log(1 + monthly_rate)
    return int(math.ceil(months))


def calculate_refinance_comparison(current_balance, current_rate, current_remaining_months,
                                 new_rate, new_term_months, closing_costs, cash_out=0):
    """
    Compare current loan vs refinancing option
    
    Returns:
        Dictionary with comparison analysis
    """
    current_monthly_rate = current_rate / 100 / 12
    new_monthly_rate = new_rate / 100 / 12
    
    # Calculate current loan remaining payments
    if current_rate == 0:
        current_payment = current_balance / current_remaining_months
    else:
        current_payment = (current_balance * current_monthly_rate * 
                         (1 + current_monthly_rate) ** current_remaining_months) / \
                         ((1 + current_monthly_rate) ** current_remaining_months - 1)
    
    current_total = current_payment * current_remaining_months
    current_interest = current_total - current_balance
    
    # Calculate new loan
    new_principal = current_balance + closing_costs + cash_out
    
    if new_rate == 0:
        new_payment = new_principal / new_term_months
    else:
        new_payment = (new_principal * new_monthly_rate * 
                      (1 + new_monthly_rate) ** new_term_months) / \
                      ((1 + new_monthly_rate) ** new_term_months - 1)
    
    new_total = new_payment * new_term_months
    new_interest = new_total - new_principal
    
    # Calculate break-even point (when refinancing pays off)
    monthly_savings = current_payment - new_payment
    if monthly_savings > 0:
        breakeven_months = closing_costs / monthly_savings
    else:
        breakeven_months = float('inf')
    
    # Total cost comparison
    total_cost_current = current_total
    total_cost_new = new_total
    total_savings = total_cost_current - total_cost_new
    
    return {
        'current_payment': round(current_payment, 2),
        'current_total_payments': round(current_total, 2),
        'current_total_interest': round(current_interest, 2),
        'new_payment': round(new_payment, 2),
        'new_total_payments': round(new_total, 2),
        'new_total_interest': round(new_interest, 2),
        'new_principal': round(new_principal, 2),
        'monthly_savings': round(monthly_savings, 2),
        'total_savings': round(total_savings, 2),
        'breakeven_months': round(breakeven_months, 1) if breakeven_months != float('inf') else None,
        'closing_costs': closing_costs,
        'cash_out': cash_out
    }


def calculate_compound_interest(principal, rate, years, monthly_contribution=0, compounding='monthly'):
    """
    Calculate compound interest with optional regular contributions
    
    Args:
        principal: Initial investment amount
        rate: Annual return rate (as percentage)
        years: Investment period in years
        monthly_contribution: Regular monthly contribution
        compounding: Compounding frequency
    
    Returns:
        Dictionary with investment growth analysis
    """
    annual_rate = rate / 100
    monthly_contrib = monthly_contribution or 0
    
    # Determine compounding periods per year
    if compounding == 'daily':
        n = 365
    elif compounding == 'monthly':
        n = 12
    elif compounding == 'quarterly':
        n = 4
    elif compounding == 'annually':
        n = 1
    else:  # continuous
        n = 1
    
    if compounding == 'continuous':
        # Continuous compounding
        future_value = principal * math.exp(annual_rate * years)
        if monthly_contrib > 0:
            # Future value of annuity with continuous compounding
            annuity_value = monthly_contrib * 12 * (math.exp(annual_rate * years) - 1) / annual_rate
            future_value += annuity_value
    else:
        # Standard compound interest
        compound_rate = annual_rate / n
        periods = n * years
        
        # Future value of principal
        future_principal = principal * (1 + compound_rate) ** periods
        
        # Future value of regular contributions (annuity)
        if monthly_contrib > 0 and annual_rate > 0:
            monthly_rate = annual_rate / 12
            monthly_periods = 12 * years
            future_contributions = monthly_contrib * (((1 + monthly_rate) ** monthly_periods - 1) / monthly_rate)
        else:
            future_contributions = monthly_contrib * 12 * years
        
        future_value = future_principal + future_contributions
    
    total_contributions = principal + (monthly_contrib * 12 * years)
    total_interest = future_value - total_contributions
    
    return {
        'future_value': round(future_value, 2),
        'total_contributions': round(total_contributions, 2),
        'total_interest': round(total_interest, 2),
        'effective_annual_rate': round(((future_value / total_contributions) ** (1/years) - 1) * 100, 2) if total_contributions > 0 else 0
    }


def calculate_debt_avalanche(loans, extra_payment):
    """
    Calculate debt payoff using avalanche method (highest interest first)
    
    Args:
        loans: QuerySet of Loan objects
        extra_payment: Additional monthly payment amount
    
    Returns:
        Dictionary with payoff strategy analysis
    """
    # Sort loans by interest rate (highest first)
    loan_list = []
    total_minimum = 0
    
    for loan in loans.order_by('-interest_rate'):
        loan_data = {
            'loan': loan,
            'balance': loan.current_balance,
            'payment': loan.monthly_payment,
            'rate': loan.interest_rate / 100 / 12,
            'payoff_month': 0
        }
        loan_list.append(loan_data)
        total_minimum += loan.monthly_payment
    
    total_available = total_minimum + extra_payment
    current_month = 0
    total_interest = 0
    
    while any(loan['balance'] > 0 for loan in loan_list):
        current_month += 1
        remaining_payment = total_available
        
        # Pay minimums first
        for loan in loan_list:
            if loan['balance'] > 0:
                interest = loan['balance'] * loan['rate']
                principal = min(loan['payment'] - interest, loan['balance'])
                loan['balance'] -= principal
                total_interest += interest
                remaining_payment -= loan['payment']
                
                if loan['balance'] <= 0:
                    loan['payoff_month'] = current_month
        
        # Apply extra payment to highest interest rate debt
        for loan in loan_list:
            if loan['balance'] > 0 and remaining_payment > 0:
                extra_principal = min(remaining_payment, loan['balance'])
                loan['balance'] -= extra_principal
                remaining_payment -= extra_principal
                
                if loan['balance'] <= 0:
                    loan['payoff_month'] = current_month
                break
    
    return {
        'method': 'Debt Avalanche',
        'total_months': current_month,
        'total_payments': total_available * current_month,
        'total_interest': round(total_interest, 2),
        'loans': loan_list
    }


def calculate_debt_snowball(loans, extra_payment):
    """
    Calculate debt payoff using snowball method (smallest balance first)
    
    Args:
        loans: QuerySet of Loan objects
        extra_payment: Additional monthly payment amount
    
    Returns:
        Dictionary with payoff strategy analysis
    """
    # Sort loans by balance (smallest first)
    loan_list = []
    total_minimum = 0
    
    for loan in loans.order_by('current_balance'):
        loan_data = {
            'loan': loan,
            'balance': loan.current_balance,
            'payment': loan.monthly_payment,
            'rate': loan.interest_rate / 100 / 12,
            'payoff_month': 0
        }
        loan_list.append(loan_data)
        total_minimum += loan.monthly_payment
    
    total_available = total_minimum + extra_payment
    current_month = 0
    total_interest = 0
    
    while any(loan['balance'] > 0 for loan in loan_list):
        current_month += 1
        remaining_payment = total_available
        
        # Pay minimums first
        for loan in loan_list:
            if loan['balance'] > 0:
                interest = loan['balance'] * loan['rate']
                principal = min(loan['payment'] - interest, loan['balance'])
                loan['balance'] -= principal
                total_interest += interest
                remaining_payment -= loan['payment']
                
                if loan['balance'] <= 0:
                    loan['payoff_month'] = current_month
        
        # Apply extra payment to smallest balance debt
        for loan in loan_list:
            if loan['balance'] > 0 and remaining_payment > 0:
                extra_principal = min(remaining_payment, loan['balance'])
                loan['balance'] -= extra_principal
                remaining_payment -= extra_principal
                
                if loan['balance'] <= 0:
                    loan['payoff_month'] = current_month
                break
    
    return {
        'method': 'Debt Snowball',
        'total_months': current_month,
        'total_payments': total_available * current_month,
        'total_interest': round(total_interest, 2),
        'loans': loan_list
    }


def calculate_lifetime_savings(existing_loan, refinance_result):
    """
    Calculate lifetime savings from refinancing considering loan history
    
    Args:
        existing_loan: Loan object that is being refinanced
        refinance_result: Result from calculate_refinance_comparison
    
    Returns:
        Dictionary with lifetime savings analysis
    """
    from django.db.models import Sum
    
    # Get total payments already made on original loan
    total_payments_made = existing_loan.payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Calculate what original loan would have cost over its full term
    original_schedule = generate_amortization_schedule(
        existing_loan.principal_amount,
        existing_loan.interest_rate,
        existing_loan.term_months,
        existing_loan.monthly_payment
    )
    
    original_total_cost = sum(payment['payment'] for payment in original_schedule)
    original_total_interest = original_total_cost - existing_loan.principal_amount
    
    # Calculate remaining cost of current loan
    current_remaining_cost = refinance_result['current_total_payments']
    
    # Calculate new loan total cost
    new_total_cost = refinance_result['new_total_payments']
    
    # Lifetime analysis
    total_original_cost = total_payments_made + current_remaining_cost
    total_new_cost = total_payments_made + new_total_cost
    
    lifetime_savings = total_original_cost - total_new_cost
    
    # Interest savings from original loan schedule
    payments_made_count = existing_loan.payments.count()
    if payments_made_count < len(original_schedule):
        remaining_interest_original = sum(
            payment['interest'] for payment in original_schedule[payments_made_count:]
        )
    else:
        remaining_interest_original = 0
    
    interest_savings = remaining_interest_original - refinance_result['new_total_interest']
    
    return {
        'original_total_cost': round(original_total_cost, 2),
        'original_total_interest': round(original_total_interest, 2),
        'total_payments_made': total_payments_made,
        'lifetime_savings': round(lifetime_savings, 2),
        'lifetime_interest_savings': round(interest_savings, 2),
        'payments_made_count': payments_made_count,
        'original_term_months': existing_loan.term_months
    }


def calculate_net_worth_projection(loans, investments, years=10):
    """
    Project net worth over time considering loan payoffs and investment growth
    
    Args:
        loans: QuerySet of active loans
        investments: QuerySet of active investments
        years: Projection period
    
    Returns:
        List of yearly net worth projections
    """
    projections = []
    
    for year in range(1, years + 1):
        # Calculate remaining loan balances
        total_loan_balance = 0
        for loan in loans:
            remaining_months = loan.get_remaining_payments()
            if remaining_months > year * 12:
                # Loan still has balance
                months_paid = year * 12
                schedule = generate_amortization_schedule(
                    loan.current_balance, 
                    loan.interest_rate, 
                    remaining_months, 
                    loan.monthly_payment
                )
                if months_paid < len(schedule):
                    total_loan_balance += schedule[months_paid]['ending_balance']
        
        # Calculate investment values
        total_investment_value = 0
        for investment in investments:
            future_value = investment.calculate_future_value(year)
            total_investment_value += future_value
        
        net_worth = total_investment_value - total_loan_balance
        
        projections.append({
            'year': year,
            'loans': round(total_loan_balance, 2),
            'investments': round(total_investment_value, 2),
            'net_worth': round(net_worth, 2)
        })
    
    return projections