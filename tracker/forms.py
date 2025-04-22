# forms.py

from django import forms
from .models import Vehicle, Event, Location, TodoItem, MaintenanceCategory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['name', 'make', 'model', 'year', 'type', 'image']
        widgets = {
            'year': forms.NumberInput(attrs={'min': 1900, 'max': 2100}),
        }


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'address']


class MaintenanceEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vehicle', 'date', 'maintenance_category', 'miles', 'hours', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(owner=user)


class GasEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vehicle', 'date', 'miles', 'gallons', 'price_per_gallon', 'total_cost', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(owner=user)
    
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
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(owner=user)
            self.fields['location'].queryset = Location.objects.filter(created_by=user)


class TodoItemForm(forms.ModelForm):
    shared_with = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'select2'})
    )
    
    class Meta:
        model = TodoItem
        fields = ['title', 'description', 'vehicle', 'shared_with']
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(owner=user)
            self.fields['shared_with'].queryset = User.objects.exclude(id=user.id)

class UserRegisterForm(UserCreationForm):
    """Extended user registration form with email field"""
    email = forms.EmailField()
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']