from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from datetime import date
from django.utils.translation import gettext_lazy as _
from .models import Family, Vehicle, Event, TodoItem, Location, MaintenanceSchedule


class FamilyForm(forms.ModelForm):
    """Form for creating and updating Family instances"""
    
    class Meta:
        model = Family
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Smith Family'})
        }


class FamilyMemberForm(forms.Form):
    """Form for adding members to a family by email"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter email address of user to add'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.family = kwargs.pop('family', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("No user found with this email address.")
        
        # Check if user is already a member
        if self.family and user in self.family.members.all():
            raise forms.ValidationError("This user is already a member of this family.")
            
        return email


class VehicleForm(forms.ModelForm):
    """Form for creating and updating Vehicle instances"""
    
    class Meta:
        model = Vehicle
        fields = ['name', 'make', 'model', 'year', 'type', 'image', 'family']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'make': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'family': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit family choices to families the user belongs to
        if user:
            self.fields['family'].queryset = user.families.all()
            
            # If user is only in one family, preselect it
            if user.families.count() == 1:
                self.fields['family'].initial = user.families.first()


class EventForm(forms.ModelForm):
    """Form for creating and updating Event instances"""
    
    class Meta:
        model = Event
        fields = [
            'vehicle', 'event_type', 'date', 'notes', 
            'miles', 'hours', 'gallons', 'price_per_gallon',
            'total_cost', 'maintenance_category', 'location'
        ]
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'event_type': forms.Select(attrs={'class': 'form-select', 'id': 'event-type-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'miles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'gallons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'price_per_gallon': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'total_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'maintenance_category': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit vehicle choices to vehicles in user's families
        if user:
            user_families = user.families.all()
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)
            
            # Limit location choices to those created by the user
            self.fields['location'].queryset = Location.objects.filter(created_by=user)


class TodoItemForm(forms.ModelForm):
    """Form for creating and updating TodoItem instances"""
    
    class Meta:
        model = TodoItem
        fields = ['title', 'description', 'vehicle', 'due_date', 'priority', 'shared_with']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'priority': forms.Select(attrs={'class': 'form-select'}, choices=[(0, 'Normal'), (1, 'Medium'), (2, 'High')]),
            'shared_with': forms.SelectMultiple(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Get all families the user belongs to
            user_families = user.families.all()
            
            # Limit vehicle choices to those in user's families
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)
            
            # Limit shared_with to family members across all user's families
            family_members = User.objects.filter(families__in=user_families).distinct().exclude(id=user.id)
            self.fields['shared_with'].queryset = family_members


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }


class MaintenanceEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vehicle', 'date', 'maintenance_category', 'miles', 'hours', 'notes']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'maintenance_category': forms.Select(attrs={'class': 'form-select'}),
            'miles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current date as default
        self.fields['date'].initial = date.today()
        
        # Limit vehicle choices to vehicles in user's families
        if user:
            user_families = user.families.all()
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)


class MaintenanceScheduleForm(forms.ModelForm):
    """
    Form for creating and updating maintenance schedules.
    """
    class Meta:
        model = MaintenanceSchedule
        fields = [
            'vehicle', 'maintenance_type', 'name', 'description',
            'interval_miles', 'interval_hours', 'interval_days',
            'last_performed', 'last_miles', 'last_hours', 'is_active'
        ]
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'interval_miles': forms.NumberInput(attrs={'class': 'form-control'}),
            'interval_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'interval_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_performed': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'last_miles': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'interval_miles': _('Miles Between Maintenance'),
            'interval_hours': _('Hours Between Maintenance'),
            'interval_days': _('Days Between Maintenance'),
            'last_performed': _('Last Performed Date'),
            'last_miles': _('Last Performed Mileage'),
            'last_hours': _('Last Performed Hours'),
            'is_active': _('Active Schedule')
        }
        help_texts = {
            'interval_miles': _('Set for vehicles tracked by mileage (cars)'),
            'interval_hours': _('Set for vehicles tracked by hours (boats)'),
            'interval_days': _('Set for time-based maintenance'),
            'name': _('Short name for this maintenance schedule'),
            'is_active': _('Uncheck to disable this schedule temporarily')
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
            
        # Filter vehicles to only those the user has access to
        if user:
            user_families = user.families.all()
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)
            
        # Set initial values based on vehicle type
        if self.instance and self.instance.pk:
            vehicle = self.instance.vehicle
            if vehicle and vehicle.type != 'car':
                self.fields['interval_miles'].widget.attrs.update({'disabled': 'disabled'})
                self.fields['last_miles'].widget.attrs.update({'disabled': 'disabled'})
            else:
                self.fields['interval_hours'].widget.attrs.update({'disabled': 'disabled'})
                self.fields['last_hours'].widget.attrs.update({'disabled': 'disabled'})
    
    def clean(self):
        cleaned_data = super().clean()
        interval_miles = cleaned_data.get('interval_miles')
        interval_hours = cleaned_data.get('interval_hours')
        interval_days = cleaned_data.get('interval_days')
        
        # Check that at least one interval is set
        if not interval_miles and not interval_hours and not interval_days:
            raise forms.ValidationError(
                "You must set at least one maintenance interval (miles, hours, or days)."
            )
        
        # Validate based on vehicle type
        vehicle = cleaned_data.get('vehicle')
        if vehicle:
            if vehicle.type == 'car' and interval_hours:
                self.add_error('interval_hours', "Hours interval is not applicable for cars.")
            elif vehicle.type != 'car' and interval_miles:
                self.add_error('interval_miles', "Miles interval is not applicable for this vehicle type.")
        
        return cleaned_data
    

class GasEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vehicle', 'date', 'miles', 'gallons', 'price_per_gallon', 'total_cost', 'notes']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'miles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'gallons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'price_per_gallon': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'total_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current date as default
        self.fields['date'].initial = date.today()
        
        # Limit vehicle choices to vehicles in user's families
        if user:
            user_families = user.families.all()
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)
            
            # Set initial vehicle to the most recently used one
            try:
                last_event = Event.objects.filter(
                    created_by=user
                ).order_by('-date', '-created_at').first()
                
                if last_event and last_event.vehicle:
                    self.fields['vehicle'].initial = last_event.vehicle.id
            except Exception:
                # If there's any error, just continue without a default vehicle
                pass

    def clean(self):
        cleaned_data = super().clean()
        gallons = cleaned_data.get('gallons')
        price_per_gallon = cleaned_data.get('price_per_gallon')
        total_cost = cleaned_data.get('total_cost')
        
        # If gallons and price_per_gallon are provided but total_cost is not,
        # calculate total_cost
        if gallons and price_per_gallon and not total_cost:
            cleaned_data['total_cost'] = gallons * price_per_gallon
        return cleaned_data


class OutingEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vehicle', 'date', 'location', 'miles', 'hours', 'notes']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'miles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current date as default
        self.fields['date'].initial = date.today()
        
        # Limit vehicle choices to vehicles in user's families
        if user:
            user_families = user.families.all()
            self.fields['vehicle'].queryset = Vehicle.objects.filter(family__in=user_families)
            
            # Limit location choices to those created by the user
            self.fields['location'].queryset = Location.objects.filter(created_by=user)
            
            # Set initial vehicle to the most recently used one
            try:
                last_event = Event.objects.filter(
                    created_by=user
                ).order_by('-date', '-created_at').first()
                
                if last_event and last_event.vehicle:
                    self.fields['vehicle'].initial = last_event.vehicle.id
            except Exception:
                # If there's any error, just continue without a default vehicle
                pass


class UserRegisterForm(UserCreationForm):
    """Extended user registration form with email field"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to the password fields
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})