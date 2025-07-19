from django.core.management.base import BaseCommand
from loans.models import LoanType, InvestmentType


class Command(BaseCommand):
    help = 'Create default loan types and investment types'

    def handle(self, *args, **options):
        # Create loan types
        loan_types = [
            ('mortgage', 'Mortgage'),
            ('auto', 'Auto Loan'),
            ('personal', 'Personal Loan'),
            ('heloc', 'HELOC'),
            ('student', 'Student Loan'),
            ('credit_card', 'Credit Card'),
            ('business', 'Business Loan'),
            ('other', 'Other'),
        ]

        for name, display_name in loan_types:
            loan_type, created = LoanType.objects.get_or_create(
                name=name,
                defaults={'description': f'{display_name} type loan'}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created loan type: {display_name}')
                )
            else:
                self.stdout.write(f'Loan type already exists: {display_name}')

        # Create investment types
        investment_types = [
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

        for name, display_name in investment_types:
            investment_type, created = InvestmentType.objects.get_or_create(
                name=name,
                defaults={'description': f'{display_name} investment'}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created investment type: {display_name}')
                )
            else:
                self.stdout.write(f'Investment type already exists: {display_name}')

        self.stdout.write(
            self.style.SUCCESS('Successfully set up loan and investment types')
        )