from django import forms

class StockForm(forms.Form):
    input_string = forms.CharField(max_length=100)
