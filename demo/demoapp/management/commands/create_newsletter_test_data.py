"""
Management command to create test data for GenericModelGroupResolver testing.

Creates 50 users with random data and 2 TestingNewsletter instances,
each with 25 different users.
"""

import random
import string

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from demoapp.models import TestingNewsletter

User = get_user_model()

FIRST_NAMES = [
    'Ana', 'Carlos', 'María', 'José', 'Laura', 'Pedro', 'Sofía', 'Miguel',
    'Valeria', 'Diego', 'Isabella', 'Andrés', 'Camila', 'Ricardo', 'Daniela',
    'Fernando', 'Paula', 'Jorge', 'Natalia', 'Alejandro', 'Gabriela', 'Héctor',
    'Mónica', 'Raúl', 'Verónica', 'Arturo', 'Patricia', 'Manuel', 'Claudia',
    'Roberto',
]

LAST_NAMES = [
    'García', 'Rodríguez', 'López', 'Martínez', 'González', 'Pérez',
    'Sánchez', 'Ramírez', 'Torres', 'Flores', 'Rivera', 'Gómez', 'Díaz',
    'Cruz', 'Morales', 'Reyes', 'Herrera', 'Medina', 'Vargas', 'Castillo',
    'Jiménez', 'Moreno', 'Ruiz', 'Gutiérrez', 'Ortiz', 'Ramos', 'Núñez',
    'Álvarez', 'Romero', 'Serrano',
]


def random_string(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


class Command(BaseCommand):
    help = 'Create 50 test users and 2 TestingNewsletter instances for resolver testing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing test users and TestingNewsletter instances first.')

    def handle(self, *args, **options):
        if options['clear']:
            TestingNewsletter.objects.all().delete()
            User.objects.filter(username__startswith='testuser_').delete()
            self.stdout.write('Cleared existing test data.')

        # Create 50 users
        self.stdout.write('Creating 50 test users...')
        created_users = []
        for i in range(50):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            suffix = random_string(4)
            username = f'testuser_{i+1:02d}_{suffix}'
            email = f'{username}@example.com'

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'is_active': True,
                }
            )
            created_users.append(user)

        self.stdout.write(self.style.SUCCESS(f'  {len(created_users)} users ready.'))

        # Split into two groups of 25
        group_a = created_users[:25]
        group_b = created_users[25:]

        # Create 2 TestingNewsletter instances
        nl1 = TestingNewsletter.objects.create()
        nl1.users.set(group_a)
        self.stdout.write(self.style.SUCCESS(
            f'  TestingNewsletter #{nl1.pk} → {nl1.users.count()} users '
            f'(address: {nl1.pk}@demoapp.testingnewsletter.groups)'))

        nl2 = TestingNewsletter.objects.create()
        nl2.users.set(group_b)
        self.stdout.write(self.style.SUCCESS(
            f'  TestingNewsletter #{nl2.pk} → {nl2.users.count()} users '
            f'(address: {nl2.pk}@demoapp.testingnewsletter.groups)'))

        self.stdout.write(self.style.SUCCESS('\nDone! Use these recipient addresses:'))
        self.stdout.write(f'  {nl1.pk}@demoapp.testingnewsletter.groups')
        self.stdout.write(f'  {nl2.pk}@demoapp.testingnewsletter.groups')
