from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


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
        return self.key + " - "+self.description


class WithCatalog(models.Model):
    mycatalog = GTForeignKey(
        Catalog, on_delete=models.DO_NOTHING, key_name="key", key_value="Options")
    countries = GTManyToManyField(
        Catalog, related_name="countryrel", key_name="key", key_value="countries")

    def __str__(self):
        return str(self.mycatalog)


class OneCatalog(models.Model):
    me = GTOneToOneField(Catalog, on_delete=models.CASCADE,
                         key_name="key", key_value="countries")

    def __str__(self):
        return str(self.me)


class Foo(models.Model):
    age = models.IntegerField(validators=[
        MaxValueValidator(120),
        MinValueValidator(1)
    ])
    speed_in_miles_per_hour = models.FloatField(validators=[
        MinValueValidator(1),
        MaxValueValidator(50)
    ])
    number_of_eyes = models.IntegerField(validators=[
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
    comunities = models.ManyToManyField('Comunity')
    country = models.ForeignKey(
        Country, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Comunity(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class A(models.Model):
    display = models.CharField(max_length=150)


class B(models.Model):
    display = models.CharField(max_length=150)
    a = models.ForeignKey(A, on_delete=models.CASCADE)


class C(models.Model):
    display = models.CharField(max_length=150)
    b = models.ForeignKey(B, on_delete=models.CASCADE)


class D(models.Model):
    display = models.CharField(max_length=150)
    c = models.ForeignKey(C, on_delete=models.CASCADE)


class E(models.Model):
    display = models.CharField(max_length=150)
    d = models.ForeignKey(D, on_delete=models.CASCADE)


class ABCDE(models.Model):
    a = models.ManyToManyField(A)
    b = models.ForeignKey(B, on_delete=models.CASCADE)
    c = models.ManyToManyField(C)
    d = models.ForeignKey(D, on_delete=models.CASCADE)
    e = models.ManyToManyField(E)

    def __str__(self):
        return " ".join([x.display for x in self.e.all()])


def validate_inputs(value):
    if value.find('_') != -1:
        raise ValidationError(
            _('%(value)s need more digits'), params={'value': value},)


def validate_email(value):
    position = value.split('@')
    if value.find('_') != -1 and len(position[0]) > 0 and len(position[1]) > 4:
        raise ValidationError(_('that email invalid'))


def validate_credit_card(value):
    position = value.split('_')
    value = position[0]
    if len(value) < 13:
        raise ValidationError(_('that card invalid'))

    return value


class InputMask(models.Model):

    date = models.DateField()
    phone = models.CharField(max_length=14, validators=[validate_inputs])
    serial_number = models.CharField(
        max_length=23, validators=[validate_inputs])
    taxid = models.CharField(max_length=11, validators=[validate_inputs])
    credit_card = models.CharField(
        max_length=19, validators=[validate_credit_card])
    email = models.EmailField(validators=[validate_email])

    def __str__(self):
        return str(self.id)+' - '+self.email


class DateRange(models.Model):

    date_range = models.CharField(max_length=25)
    date_custom = models.CharField(max_length=25)
    date_time = models.CharField(max_length=45)


class gridSlider(models.Model):
    minimum= models.IntegerField()
    maximum= models.IntegerField()
    datetime = models.DateTimeField()
    age= models.IntegerField()

class Contact(models.Model):
    number=models.CharField(max_length=20)