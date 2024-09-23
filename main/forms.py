from django.core.exceptions import ValidationError
from django import forms
from main.models import ParrentTransaction, TransferUser, Customer, Transaction

class ParrentTransactionAdminForm(forms.ModelForm):
    type = forms.ChoiceField(choices = [
        (0, "-------"),
        (5, "Transaksi Dibakar"),
        (6, "Transaksi Ditarik"),
    ])
    
    class Meta:
        model = ParrentTransaction
        fields = ('customer', 'child_transaction_id', 'amount', 'caption', 'type', 'time')

    def clean_amount(self):
        data = self.cleaned_data['amount']
        type_ = int(self.data['type'])
        if type_ in [ParrentTransaction.TypeChoices.BURN_TRANSACTION, ParrentTransaction.TypeChoices.WITHDRAW_TRANSACTION]:
            if data >= 0:
                raise ValidationError("harus negatif")
            
        # di validasi di constraint
        return data
    
    def clean_child_transaction_id(self):
        data = self.cleaned_data['child_transaction_id']
        type_ = int(self.data['type'])
        if type_ in [ParrentTransaction.TypeChoices.BURN_TRANSACTION, ParrentTransaction.TypeChoices.WITHDRAW_TRANSACTION]:
            if data != None:
                raise ValidationError("harus kosong")
            
        # di validasi di constraint
        return data


class TransferUserAdminForm(forms.ModelForm):
    class Meta:
        model = TransferUser
        fields = '__all__'
    
    def clean_from_customer(self):
        data = self.cleaned_data['from_customer']
        if data.type != Customer.TypeChoices.USER:
            raise ValidationError("harus user")
        
        return data
    
    def clean_to_customer(self):
        data = self.cleaned_data['to_customer']
        if data.type != Customer.TypeChoices.USER:
            raise ValidationError("harus user")
        
        return data
    
    
class TransactionMerchantAdminForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = '__all__'
    
    def clean_from_customer(self):
        data = self.cleaned_data['from_customer']
        if data.type != Customer.TypeChoices.USER:
            raise ValidationError("harus user")
        
        return data
    
    def clean_to_customer(self):
        data = self.cleaned_data['to_customer']
        if data.type != Customer.TypeChoices.MERCHANT:
            raise ValidationError("harus merchant")
        
        return data