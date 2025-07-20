from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta
from .models import Loan, LoanType, Payment, Investment, InvestmentType, InvestmentTransaction


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = [
            'name', 'loan_type', 'lender', 'account_number',
            'principal_amount', 'interest_rate', 'term_months',
            'payment_type', 'monthly_payment', 'payment_frequency',
            'start_date', 'first_payment_date', 'maturity_date',
            'is_variable_rate', 'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'first_payment_date': forms.DateInput(attrs={'type': 'date'}),
            'maturity_date': forms.DateInput(attrs={'type': 'date'}),
            'principal_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'interest_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'monthly_payment': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'term_months': forms.NumberInput(attrs={'min': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['loan_type'].queryset = LoanType.objects.all()
        self.fields['loan_type'].empty_label = "Select loan type"
        
        # Make monthly_payment optional - it will be calculated if not provided
        self.fields['monthly_payment'].required = False
        self.fields['maturity_date'].required = False
        
        # Update field labels and help text based on payment type
        self.fields['payment_type'].help_text = "Automatic: Regular scheduled payments. Manual: Sporadic payments with interest calculated daily."
        self.fields['monthly_payment'].help_text = "For automatic: scheduled payment amount. For manual: typical/minimum payment amount."
        self.fields['first_payment_date'].help_text = "For automatic: first scheduled payment. For manual: approximate first payment date."

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        first_payment_date = cleaned_data.get('first_payment_date')
        
        if start_date and first_payment_date:
            if first_payment_date < start_date:
                raise ValidationError("First payment date cannot be before loan start date.")
        
        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'payment_date', 'amount', 'principal_amount', 'interest_amount',
            'escrow_amount', 'payment_type', 'notes'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'principal_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'interest_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'escrow_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.loan = kwargs.pop('loan', None)
        super().__init__(*args, **kwargs)
        
        # Set default payment date to today
        if not self.instance.pk:
            self.fields['payment_date'].initial = date.today()
        
        # Make principal and interest optional - they'll be calculated if not provided
        self.fields['principal_amount'].required = False
        self.fields['interest_amount'].required = False

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        principal = cleaned_data.get('principal_amount') or Decimal('0')
        interest = cleaned_data.get('interest_amount') or Decimal('0')
        escrow = cleaned_data.get('escrow_amount') or Decimal('0')
        
        if amount and (principal + interest + escrow) > amount:
            raise ValidationError("Principal + Interest + Escrow cannot exceed total payment amount.")
        
        return cleaned_data


class ManualPaymentForm(forms.ModelForm):
    """Special form for manual payment loans with automatic interest calculation"""
    
    class Meta:
        model = Payment
        fields = [
            'payment_date', 'amount', 'notes'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.loan = kwargs.pop('loan', None)
        super().__init__(*args, **kwargs)
        
        # Set default payment date to today
        if not self.instance.pk:
            self.fields['payment_date'].initial = date.today()
        
        # Add help text about automatic calculation
        if self.loan and self.loan.payment_type == 'manual':
            accrued_interest = self.loan.calculate_accrued_interest()
            self.fields['amount'].help_text = f"Interest accrued to date: ${accrued_interest:.2f}. Principal and interest will be calculated automatically."

    def save(self, commit=True):
        payment = super().save(commit=False)
        
        if self.loan and self.loan.payment_type == 'manual':
            # Calculate payment breakdown for manual loans
            breakdown = self.loan.get_next_payment_breakdown(payment.amount)
            if breakdown:
                payment.interest_amount = breakdown['interest_portion']
                payment.principal_amount = breakdown['principal_portion']
                payment.payment_type = 'manual'
        
        if commit:
            payment.save()
            # Update loan balance for manual payment loans
            if self.loan and self.loan.payment_type == 'manual':
                self.loan.update_balance_after_payment(payment.amount, payment.payment_date)
        
        return payment


class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = [
            'name', 'investment_type', 'institution', 'account_number',
            'initial_amount', 'target_amount', 'annual_return_rate',
            'compounding_frequency', 'monthly_contribution',
            'start_date', 'maturity_date', 'is_tax_advantaged', 'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'maturity_date': forms.DateInput(attrs={'type': 'date'}),
            'initial_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'target_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'annual_return_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '-100', 'max': '100'}),
            'monthly_contribution': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['investment_type'].queryset = InvestmentType.objects.all()
        self.fields['investment_type'].empty_label = "Select investment type"
        
        # Make some fields optional
        self.fields['target_amount'].required = False
        self.fields['maturity_date'].required = False


class InvestmentTransactionForm(forms.ModelForm):
    class Meta:
        model = InvestmentTransaction
        fields = [
            'transaction_date', 'transaction_type', 'amount',
            'shares', 'price_per_share', 'notes'
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'shares': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'price_per_share': forms.NumberInput(attrs={'step': '0.0001', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default transaction date to today
        if not self.instance.pk:
            self.fields['transaction_date'].initial = date.today()
        
        # Make shares and price optional
        self.fields['shares'].required = False
        self.fields['price_per_share'].required = False


# Calculator Forms
class LoanCalculatorForm(forms.Form):
    principal_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Loan Amount",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})
    )
    annual_interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        label="Annual Interest Rate (%)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'})
    )
    term_months = forms.IntegerField(
        min_value=1,
        max_value=480,  # 40 years
        label="Term (Months)",
        widget=forms.NumberInput(attrs={'min': '1', 'max': '480'})
    )
    desired_monthly_payment = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        label="Desired Monthly Payment (Optional)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        help_text="Enter a higher payment to see potential savings"
    )
    generate_schedule = forms.BooleanField(
        required=False,
        label="Generate Amortization Schedule",
        widget=forms.CheckboxInput()
    )


class ExtraPaymentCalculatorForm(forms.Form):
    current_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Current Balance",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})
    )
    annual_interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        label="Annual Interest Rate (%)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'})
    )
    current_monthly_payment = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Current Monthly Payment",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})
    )
    extra_monthly_payment = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        label="Extra Monthly Payment",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    lump_sum_payment = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        label="One-time Lump Sum Payment (Optional)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )


class RefinanceCalculatorForm(forms.Form):
    existing_loan = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="Or enter loan details manually below",
        label="Select Existing Loan (Optional)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    current_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Current Balance",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})
    )
    current_interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        label="Current Interest Rate (%)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'})
    )
    current_remaining_months = forms.IntegerField(
        min_value=1,
        max_value=480,
        label="Current Remaining Months",
        widget=forms.NumberInput(attrs={'min': '1', 'max': '480'})
    )
    new_interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        label="New Interest Rate (%)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'})
    )
    new_term_months = forms.IntegerField(
        min_value=1,
        max_value=480,
        label="New Term (Months)",
        widget=forms.NumberInput(attrs={'min': '1', 'max': '480'})
    )
    closing_costs = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        label="Closing Costs",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    cash_out_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        label="Cash Out Amount (Optional)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )

    def __init__(self, *args, **kwargs):
        user_family = kwargs.pop('user_family', None)
        super().__init__(*args, **kwargs)
        
        if user_family:
            from .models import Loan
            self.fields['existing_loan'].queryset = Loan.objects.filter(
                family=user_family, 
                status='active'
            ).select_related('loan_type')
        
        # Make current loan fields optional when selecting existing loan
        self.fields['current_balance'].required = False
        self.fields['current_interest_rate'].required = False
        self.fields['current_remaining_months'].required = False


class InvestmentCalculatorForm(forms.Form):
    COMPOUNDING_CHOICES = [
        ('daily', 'Daily'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
        ('continuous', 'Continuous'),
    ]
    
    initial_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0'),
        label="Initial Investment",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    annual_return_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('-100'),
        max_value=Decimal('100'),
        label="Annual Return Rate (%)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '-100', 'max': '100'})
    )
    investment_years = forms.IntegerField(
        min_value=1,
        max_value=50,
        label="Investment Period (Years)",
        widget=forms.NumberInput(attrs={'min': '1', 'max': '50'})
    )
    monthly_contribution = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        label="Monthly Contribution (Optional)",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    compounding_frequency = forms.ChoiceField(
        choices=COMPOUNDING_CHOICES,
        initial='monthly',
        label="Compounding Frequency",
        widget=forms.Select()
    )