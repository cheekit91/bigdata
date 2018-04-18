from __future__ import unicode_literals

from django.db import models

# Create your models here.

class Stock(models.Model):
    input_string = models.CharField(max_length=200)
