from django.db import models

# Create your models here.

class Country(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

class Person(models.Model):
    name = models.CharField(max_length=150)
    num_children = models.IntegerField(default=0)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    born_date = models.DateField()
    last_time = models.DateTimeField()

    def __str__(self):
        return self.name

class Foo(models.Model):
    age = models.IntegerField()
    speed_in_miles_per_hour = models.FloatField()
    number_of_eyes = models.IntegerField()