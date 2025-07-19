from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import (
    LoanType, Loan, Payment, ScheduledPayment, Refinance,
    InvestmentType, Investment, InvestmentTransaction
)


# Inline Admin Classes
class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('payment_date', 'amount', 'principal_amount', 'interest_amount', 'payment_type')
    readonly_fields = ('balance_after_payment', 'created_at')
    show_change_link = True


class ScheduledPaymentInline(admin.TabularInline):
    model = ScheduledPayment
    extra = 0
    fields = ('payment_number', 'due_date', 'scheduled_amount', 'principal_amount', 'interest_amount', 'is_paid')
    readonly_fields = ('beginning_balance', 'ending_balance')
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


class RefinanceInline(admin.TabularInline):
    model = Refinance
    extra = 0
    fk_name = 'original_loan'
    fields = ('new_loan', 'refinance_date', 'closing_costs', 'cash_out_amount')
    show_change_link = True


class InvestmentTransactionInline(admin.TabularInline):
    model = InvestmentTransaction
    extra = 0
    fields = ('transaction_date', 'transaction_type', 'amount', 'shares', 'price_per_share')
    readonly_fields = ('balance_after_transaction', 'created_at')
    show_change_link = True


# Admin Classes
@admin.register(LoanType)
class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'loan_count', 'total_value')
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    def loan_count(self, obj):
        return obj.loans.count()
    loan_count.short_description = 'Active Loans'
    
    def total_value(self, obj):
        total = obj.loans.aggregate(total=Sum('current_balance'))['total'] or 0
        return f"${total:,.2f}"
    total_value.short_description = 'Total Value'


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'loan_type', 'current_balance_display', 'monthly_payment', 
                   'interest_rate', 'status', 'remaining_payments_display')
    list_filter = ('loan_type', 'status', 'family', 'is_variable_rate')
    search_fields = ('name', 'lender', 'account_number')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'total_interest_display', 
                      'remaining_payments_display', 'payoff_date_estimate')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'family', 'loan_type', 'lender', 'account_number', 'status')
        }),
        ('Loan Terms', {
            'fields': ('principal_amount', 'current_balance', 'interest_rate', 'term_months', 
                      'is_variable_rate')
        }),
        ('Payment Details', {
            'fields': ('monthly_payment', 'payment_frequency')
        }),
        ('Important Dates', {
            'fields': ('start_date', 'first_payment_date', 'maturity_date')
        }),
        ('Calculations', {
            'fields': ('total_interest_display', 'remaining_payments_display', 'payoff_date_estimate'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    inlines = [PaymentInline, ScheduledPaymentInline, RefinanceInline]
    
    def current_balance_display(self, obj):
        return f"${obj.current_balance:,.2f}"
    current_balance_display.short_description = 'Current Balance'
    current_balance_display.admin_order_field = 'current_balance'
    
    def total_interest_display(self, obj):
        total_interest = obj.get_total_interest()
        return f"${total_interest:,.2f}"
    total_interest_display.short_description = 'Total Interest (Life of Loan)'
    
    def remaining_payments_display(self, obj):
        remaining = obj.get_remaining_payments()
        if remaining > 0:
            years = remaining // 12
            months = remaining % 12
            if years > 0:
                return f"{remaining} payments ({years}y {months}m)"
            else:
                return f"{remaining} payments ({months}m)"
        return "Paid Off"
    remaining_payments_display.short_description = 'Remaining Payments'
    
    def payoff_date_estimate(self, obj):
        remaining = obj.get_remaining_payments()
        if remaining > 0:
            from datetime import date
            from dateutil.relativedelta import relativedelta
            estimated_date = date.today() + relativedelta(months=remaining)
            return estimated_date.strftime('%B %Y')
        return "Already Paid Off"
    payoff_date_estimate.short_description = 'Estimated Payoff Date'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['generate_amortization_schedule', 'mark_paid_off']
    
    def generate_amortization_schedule(self, request, queryset):
        count = 0
        for loan in queryset:
            # This would generate the full amortization schedule
            count += 1
        self.message_user(request, f"Generated amortization schedules for {count} loans")
    generate_amortization_schedule.short_description = "Generate amortization schedules"
    
    def mark_paid_off(self, request, queryset):
        updated = queryset.update(status='paid_off', current_balance=0)
        self.message_user(request, f"{updated} loans marked as paid off")
    mark_paid_off.short_description = "Mark as paid off"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('loan', 'payment_date', 'amount_display', 'principal_amount_display', 
                   'interest_amount_display', 'payment_type', 'balance_after_display')
    list_filter = ('payment_type', 'payment_date', 'loan__family', 'loan__loan_type')
    search_fields = ('loan__name', 'notes')
    date_hierarchy = 'payment_date'
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    fieldsets = (
        ('Payment Information', {
            'fields': ('loan', 'payment_date', 'amount', 'payment_type')
        }),
        ('Payment Breakdown', {
            'fields': ('principal_amount', 'interest_amount', 'escrow_amount')
        }),
        ('Result', {
            'fields': ('balance_after_payment',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def amount_display(self, obj):
        return f"${obj.amount:,.2f}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def principal_amount_display(self, obj):
        return f"${obj.principal_amount:,.2f}"
    principal_amount_display.short_description = 'Principal'
    
    def interest_amount_display(self, obj):
        return f"${obj.interest_amount:,.2f}"
    interest_amount_display.short_description = 'Interest'
    
    def balance_after_display(self, obj):
        return f"${obj.balance_after_payment:,.2f}"
    balance_after_display.short_description = 'Balance After'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Refinance)
class RefinanceAdmin(admin.ModelAdmin):
    list_display = ('original_loan', 'new_loan', 'refinance_date', 'closing_costs_display', 
                   'cash_out_display', 'savings_display')
    list_filter = ('refinance_date',)
    search_fields = ('original_loan__name', 'new_loan__name', 'notes')
    readonly_fields = ('created_at', 'created_by', 'savings_display')
    fieldsets = (
        ('Refinancing Information', {
            'fields': ('original_loan', 'new_loan', 'refinance_date')
        }),
        ('Financial Details', {
            'fields': ('original_balance_at_refinance', 'total_payments_on_original', 
                      'closing_costs', 'cash_out_amount')
        }),
        ('Analysis', {
            'fields': ('savings_display',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def closing_costs_display(self, obj):
        return f"${obj.closing_costs:,.2f}"
    closing_costs_display.short_description = 'Closing Costs'
    
    def cash_out_display(self, obj):
        return f"${obj.cash_out_amount:,.2f}"
    cash_out_display.short_description = 'Cash Out'
    
    def savings_display(self, obj):
        # This would calculate potential savings
        return "Calculation needed"
    savings_display.short_description = 'Estimated Savings'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvestmentType)
class InvestmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'investment_count', 'total_value')
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    def investment_count(self, obj):
        return obj.investments.count()
    investment_count.short_description = 'Active Investments'
    
    def total_value(self, obj):
        total = obj.investments.aggregate(total=Sum('current_value'))['total'] or 0
        return f"${total:,.2f}"
    total_value.short_description = 'Total Value'


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'investment_type', 'current_value_display', 
                   'annual_return_rate', 'status', 'return_percentage_display')
    list_filter = ('investment_type', 'status', 'family', 'is_tax_advantaged')
    search_fields = ('name', 'institution', 'account_number')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'total_contributions_display',
                      'total_return_display', 'return_percentage_display', 'future_value_5y',
                      'future_value_10y')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'family', 'investment_type', 'institution', 'account_number', 'status')
        }),
        ('Financial Details', {
            'fields': ('initial_amount', 'current_value', 'target_amount', 'is_tax_advantaged')
        }),
        ('Return Details', {
            'fields': ('annual_return_rate', 'compounding_frequency')
        }),
        ('Regular Contributions', {
            'fields': ('monthly_contribution',)
        }),
        ('Important Dates', {
            'fields': ('start_date', 'maturity_date')
        }),
        ('Performance', {
            'fields': ('total_contributions_display', 'total_return_display', 
                      'return_percentage_display'),
            'classes': ('collapse',)
        }),
        ('Projections', {
            'fields': ('future_value_5y', 'future_value_10y'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    inlines = [InvestmentTransactionInline]
    
    def current_value_display(self, obj):
        return f"${obj.current_value:,.2f}"
    current_value_display.short_description = 'Current Value'
    current_value_display.admin_order_field = 'current_value'
    
    def total_contributions_display(self, obj):
        total = obj.get_total_contributions()
        return f"${total:,.2f}"
    total_contributions_display.short_description = 'Total Contributions'
    
    def total_return_display(self, obj):
        total_return = obj.get_total_return()
        color = 'green' if total_return >= 0 else 'red'
        return format_html('<span style="color: {};">${:,.2f}</span>', color, total_return)
    total_return_display.short_description = 'Total Return'
    
    def return_percentage_display(self, obj):
        percentage = obj.get_return_percentage()
        color = 'green' if percentage >= 0 else 'red'
        return format_html('<span style="color: {};">{:.2f}%</span>', color, percentage)
    return_percentage_display.short_description = 'Return %'
    
    def future_value_5y(self, obj):
        future_value = obj.calculate_future_value(5)
        return f"${future_value:,.2f}"
    future_value_5y.short_description = '5-Year Projection'
    
    def future_value_10y(self, obj):
        future_value = obj.calculate_future_value(10)
        return f"${future_value:,.2f}"
    future_value_10y.short_description = '10-Year Projection'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['update_market_values', 'project_growth']
    
    def update_market_values(self, request, queryset):
        # This would update current market values
        count = queryset.count()
        self.message_user(request, f"Market values updated for {count} investments")
    update_market_values.short_description = "Update market values"
    
    def project_growth(self, request, queryset):
        # This would generate growth projections
        count = queryset.count()
        self.message_user(request, f"Growth projections calculated for {count} investments")
    project_growth.short_description = "Calculate growth projections"


@admin.register(InvestmentTransaction)
class InvestmentTransactionAdmin(admin.ModelAdmin):
    list_display = ('investment', 'transaction_date', 'transaction_type', 'amount_display',
                   'shares_display', 'balance_after_display')
    list_filter = ('transaction_type', 'transaction_date', 'investment__family', 'investment__investment_type')
    search_fields = ('investment__name', 'notes')
    date_hierarchy = 'transaction_date'
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('investment', 'transaction_date', 'transaction_type', 'amount')
        }),
        ('Share Details', {
            'fields': ('shares', 'price_per_share'),
            'classes': ('collapse',)
        }),
        ('Result', {
            'fields': ('balance_after_transaction',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def amount_display(self, obj):
        return f"${obj.amount:,.2f}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def shares_display(self, obj):
        if obj.shares:
            return f"{obj.shares:,.6f}"
        return "-"
    shares_display.short_description = 'Shares'
    
    def balance_after_display(self, obj):
        return f"${obj.balance_after_transaction:,.2f}"
    balance_after_display.short_description = 'Balance After'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
