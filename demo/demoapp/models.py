from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


# Create your models here.
from djgentelella.fields.catalog import GTForeignKey, GTManyToManyField, GTOneToOneField


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

class Catalog(models.Model):
    key = models.CharField(max_length=150)
    description = models.CharField(max_length=500)

    def __str__(self):
        return self.key +" - "+self.description


class WithCatalog(models.Model):
    mycatalog = GTForeignKey(Catalog, on_delete=models.DO_NOTHING, key_name="key", key_value="Options")
    countries = GTManyToManyField(Catalog, related_name="countryrel", key_name="key", key_value="countries")

    def __str__(self):
        return str(self.mycatalog)

class OneCatalog(models.Model):
    me = GTOneToOneField(Catalog, on_delete=models.CASCADE, key_name="key", key_value="countries")

    def __str__(self):
        return str(self.me)

class Foo(models.Model):
    age = models.IntegerField(validators=
                                    [
                                        MaxValueValidator(120),
                                        MinValueValidator(1)
                                    ])
    speed_in_miles_per_hour = models.FloatField(validators=
                                    [
                                        MinValueValidator(1),
                                        MaxValueValidator(50)
                                    ])
    number_of_eyes = models.IntegerField(validators=
                                    [
                                        MinValueValidator(0),
                                        MaxValueValidator(10)
                                    ])

class Colors(models.Model):
    color = models.CharField(max_length=150)
    color2 = models.CharField(max_length=150)
    color3 = models.CharField(max_length=150)
    color4 = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.color} {self.color2} {self.color3} {self.color4}"


class PeopleGroup(models.Model):
    name = models.CharField(max_length=150)
    people = models.ManyToManyField(Person)

    def __str__(self):
        return self.name