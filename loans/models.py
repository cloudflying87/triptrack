from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class LoanType(models.Model):
    """Categories for different types of loans"""
    TYPE_CHOICES = [
        ('mortgage', 'Mortgage'),
        ('auto', 'Auto Loan'),
        ('personal', 'Personal Loan'),
        ('heloc', 'HELOC'),
        ('student', 'Student Loan'),
        ('credit_card', 'Credit Card'),
        ('business', 'Business Loan'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        ordering = ['name']


class Loan(models.Model):
    """Main loan model storing loan details and terms"""
    PAYMENT_FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('bi_weekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paid_off', 'Paid Off'),
        ('refinanced', 'Refinanced'),
        ('default', 'Default'),
    ]
    
    # Ownership and identification
    family = models.ForeignKey('tracker.Family', on_delete=models.CASCADE, related_name='loans')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_loans')
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT, related_name='loans')
    
    # Basic loan details
    name = models.CharField(max_length=200, help_text="Descriptive name for the loan")
    lender = models.CharField(max_length=200, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Financial terms
    principal_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Original loan amount"
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current outstanding balance"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0000')), MaxValueValidator(Decimal('99.9999'))],
        help_text="Annual interest rate as decimal (e.g., 5.25 for 5.25%)"
    )
    term_months = models.PositiveIntegerField(
        help_text="Original loan term in months"
    )
    
    # Payment details
    monthly_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Scheduled monthly payment amount"
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default='monthly'
    )
    
    # Important dates
    start_date = models.DateField(help_text="Loan origination date")
    first_payment_date = models.DateField(help_text="Date of first payment")
    maturity_date = models.DateField(help_text="Scheduled payoff date")
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_variable_rate = models.BooleanField(default=False)
    
    # Optional fields
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.loan_type} (${self.current_balance:,.2f})"
    
    def calculate_monthly_payment(self):
        """Calculate the standard monthly payment using loan formula"""
        if self.interest_rate == 0:
            return self.principal_amount / self.term_months
        
        monthly_rate = self.interest_rate / 100 / 12
        payment = (self.principal_amount * monthly_rate * 
                  (1 + monthly_rate) ** self.term_months) / \
                  ((1 + monthly_rate) ** self.term_months - 1)
        return round(payment, 2)
    
    def get_total_interest(self):
        """Calculate total interest over life of loan with standard payments"""
        return (self.monthly_payment * self.term_months) - self.principal_amount
    
    def get_remaining_payments(self):
        """Calculate remaining payments based on current balance"""
        if self.interest_rate == 0:
            return int(self.current_balance / self.monthly_payment)
        
        monthly_rate = self.interest_rate / 100 / 12
        if monthly_rate == 0:
            return int(self.current_balance / self.monthly_payment)
        
        # Calculate remaining payments using formula
        import math
        remaining = math.log(1 + (self.current_balance * monthly_rate) / self.monthly_payment) / math.log(1 + monthly_rate)
        return max(0, int(math.ceil(remaining)))
    
    def save(self, *args, **kwargs):
        # Auto-calculate monthly payment if not provided
        if not self.monthly_payment:
            self.monthly_payment = self.calculate_monthly_payment()
        
        # Auto-calculate maturity date if not provided
        if not self.maturity_date and self.first_payment_date:
            self.maturity_date = self.first_payment_date + timedelta(days=30 * self.term_months)
        
        super().save(*args, **kwargs)
    
    class Meta:
        indexes = [
            models.Index(fields=['family', 'status']),
            models.Index(fields=['loan_type', 'status']),
            models.Index(fields=['created_by', 'status']),
        ]
        ordering = ['-created_at']


class Payment(models.Model):
    """Record of actual payments made on loans"""
    PAYMENT_TYPE_CHOICES = [
        ('scheduled', 'Scheduled Payment'),
        ('extra_principal', 'Extra Principal'),
        ('extra_payment', 'Extra Payment'),
        ('lump_sum', 'Lump Sum'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_payments')
    
    # Payment details
    payment_date = models.DateField()
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    principal_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount applied to principal"
    )
    interest_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount applied to interest"
    )
    escrow_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount for escrow (taxes, insurance)"
    )
    
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='scheduled')
    
    # Tracking
    balance_after_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Remaining balance after this payment"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.loan.name} - ${self.amount} on {self.payment_date}"
    
    def save(self, *args, **kwargs):
        # Calculate principal/interest split if not provided
        if not self.principal_amount and not self.interest_amount:
            monthly_rate = self.loan.interest_rate / 100 / 12
            interest = self.loan.current_balance * monthly_rate
            self.interest_amount = min(interest, self.amount - self.escrow_amount)
            self.principal_amount = self.amount - self.interest_amount - self.escrow_amount
        
        # Calculate balance after payment
        if not self.balance_after_payment:
            self.balance_after_payment = self.loan.current_balance - self.principal_amount
        
        super().save(*args, **kwargs)
        
        # Update loan's current balance
        self.loan.current_balance = self.balance_after_payment
        if self.loan.current_balance <= 0:
            self.loan.status = 'paid_off'
        self.loan.save(update_fields=['current_balance', 'status'])
    
    class Meta:
        indexes = [
            models.Index(fields=['loan', 'payment_date']),
            models.Index(fields=['payment_type']),
        ]
        ordering = ['-payment_date']


class ScheduledPayment(models.Model):
    """Auto-generated payment schedule for loans"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='scheduled_payments')
    
    # Payment schedule details
    payment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    scheduled_amount = models.DecimalField(max_digits=10, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=10, decimal_places=2)
    escrow_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Balance tracking
    beginning_balance = models.DecimalField(max_digits=12, decimal_places=2)
    ending_balance = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status tracking
    is_paid = models.BooleanField(default=False)
    actual_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.loan.name} - Payment #{self.payment_number} (${self.scheduled_amount})"
    
    class Meta:
        indexes = [
            models.Index(fields=['loan', 'payment_number']),
            models.Index(fields=['due_date']),
        ]
        ordering = ['payment_number']
        unique_together = ['loan', 'payment_number']


class Refinance(models.Model):
    """Track loan refinancing history"""
    original_loan = models.ForeignKey(
        Loan, 
        on_delete=models.CASCADE, 
        related_name='refinances_as_original'
    )
    new_loan = models.ForeignKey(
        Loan, 
        on_delete=models.CASCADE, 
        related_name='refinances_as_new'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Refinancing details
    refinance_date = models.DateField()
    closing_costs = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cash_out_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cash taken out during refinance"
    )
    
    # Tracking
    original_balance_at_refinance = models.DecimalField(max_digits=12, decimal_places=2)
    total_payments_on_original = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total amount paid on original loan"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Refinance: {self.original_loan.name} → {self.new_loan.name}"
    
    def calculate_savings(self):
        """Calculate potential savings from refinancing"""
        # This would need complex calculations comparing payment schedules
        pass
    
    class Meta:
        ordering = ['-refinance_date']


class InvestmentType(models.Model):
    """Categories for different types of investments"""
    TYPE_CHOICES = [
        ('stocks', 'Stocks'),
        ('bonds', 'Bonds'),
        ('mutual_funds', 'Mutual Funds'),
        ('etf', 'ETF'),
        ('retirement_401k', '401(k)'),
        ('retirement_ira', 'IRA'),
        ('retirement_roth', 'Roth IRA'),
        ('savings', 'Savings Account'),
        ('cd', 'Certificate of Deposit'),
        ('real_estate', 'Real Estate'),
        ('crypto', 'Cryptocurrency'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        ordering = ['name']


class Investment(models.Model):
    """Main investment model for tracking investment accounts"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('matured', 'Matured'),
        ('transferred', 'Transferred'),
    ]
    
    COMPOUNDING_CHOICES = [
        ('daily', 'Daily'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
        ('continuous', 'Continuous'),
    ]
    
    # Ownership and identification
    family = models.ForeignKey('tracker.Family', on_delete=models.CASCADE, related_name='investments')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_investments')
    investment_type = models.ForeignKey(InvestmentType, on_delete=models.PROTECT, related_name='investments')
    
    # Basic investment details
    name = models.CharField(max_length=200, help_text="Descriptive name for the investment")
    institution = models.CharField(max_length=200, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Financial details
    initial_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Initial investment amount"
    )
    current_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current market value"
    )
    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Target investment goal"
    )
    
    # Interest/Return details
    annual_return_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('-99.9999')), MaxValueValidator(Decimal('99.9999'))],
        help_text="Expected annual return rate as decimal (e.g., 7.5 for 7.5%)"
    )
    compounding_frequency = models.CharField(
        max_length=20,
        choices=COMPOUNDING_CHOICES,
        default='monthly'
    )
    
    # Regular contribution details
    monthly_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Regular monthly contribution amount"
    )
    
    # Important dates
    start_date = models.DateField(help_text="Investment start date")
    maturity_date = models.DateField(blank=True, null=True, help_text="Investment maturity date (if applicable)")
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_tax_advantaged = models.BooleanField(default=False, help_text="401k, IRA, etc.")
    
    # Optional fields
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.investment_type} (${self.current_value:,.2f})"
    
    def calculate_future_value(self, years):
        """Calculate future value with compound interest and regular contributions"""
        from decimal import Decimal
        import math
        
        principal = float(self.current_value)
        rate = float(self.annual_return_rate) / 100
        contribution = float(self.monthly_contribution)
        
        # Get compounding periods per year
        if self.compounding_frequency == 'daily':
            n = 365
        elif self.compounding_frequency == 'monthly':
            n = 12
        elif self.compounding_frequency == 'quarterly':
            n = 4
        elif self.compounding_frequency == 'annually':
            n = 1
        else:  # continuous
            n = 1
        
        if self.compounding_frequency == 'continuous':
            # Continuous compounding with regular contributions
            future_value = principal * math.exp(rate * years)
            if contribution > 0:
                future_value += contribution * 12 * (math.exp(rate * years) - 1) / rate
        else:
            # Standard compound interest
            compound_rate = rate / n
            periods = n * years
            
            # Future value of principal
            future_principal = principal * (1 + compound_rate) ** periods
            
            # Future value of regular contributions (annuity)
            if contribution > 0 and rate > 0:
                monthly_rate = rate / 12
                monthly_periods = 12 * years
                future_contributions = contribution * (((1 + monthly_rate) ** monthly_periods - 1) / monthly_rate)
            else:
                future_contributions = contribution * 12 * years
            
            future_value = future_principal + future_contributions
        
        return Decimal(str(round(future_value, 2)))
    
    def get_total_contributions(self):
        """Calculate total contributions made to this investment"""
        total = self.initial_amount
        total += sum(t.amount for t in self.transactions.filter(transaction_type='deposit'))
        total -= sum(t.amount for t in self.transactions.filter(transaction_type='withdrawal'))
        return total
    
    def get_total_return(self):
        """Calculate total return (current value - total contributions)"""
        return self.current_value - self.get_total_contributions()
    
    def get_return_percentage(self):
        """Calculate return percentage"""
        total_contributions = self.get_total_contributions()
        if total_contributions > 0:
            return ((self.current_value - total_contributions) / total_contributions * 100)
        return Decimal('0.00')
    
    class Meta:
        indexes = [
            models.Index(fields=['family', 'status']),
            models.Index(fields=['investment_type', 'status']),
            models.Index(fields=['created_by', 'status']),
        ]
        ordering = ['-created_at']


class InvestmentTransaction(models.Model):
    """Record of transactions for investments"""
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit/Contribution'),
        ('withdrawal', 'Withdrawal'),
        ('dividend', 'Dividend/Interest'),
        ('fee', 'Fee'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('value_adjustment', 'Market Value Adjustment'),
    ]
    
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='transactions')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_investment_transactions')
    
    # Transaction details
    transaction_date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Market value tracking
    shares = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Number of shares (if applicable)"
    )
    price_per_share = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Price per share at transaction"
    )
    
    # Tracking
    balance_after_transaction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Investment value after this transaction"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.investment.name} - {self.get_transaction_type_display()} ${self.amount} on {self.transaction_date}"
    
    def save(self, *args, **kwargs):
        # Update investment current value for deposits/withdrawals
        if self.transaction_type in ['deposit', 'withdrawal']:
            if self.transaction_type == 'deposit':
                self.balance_after_transaction = self.investment.current_value + self.amount
            else:  # withdrawal
                self.balance_after_transaction = self.investment.current_value - self.amount
        
        super().save(*args, **kwargs)
        
        # Update investment's current value for certain transaction types
        if self.transaction_type in ['deposit', 'withdrawal', 'value_adjustment']:
            self.investment.current_value = self.balance_after_transaction
            self.investment.save(update_fields=['current_value'])
    
    class Meta:
        indexes = [
            models.Index(fields=['investment', 'transaction_date']),
            models.Index(fields=['transaction_type']),
        ]
        ordering = ['-transaction_date']
