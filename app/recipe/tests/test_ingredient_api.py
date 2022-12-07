"""
Tests for the ingredients API.
"""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient, Recipe

from recipe.serializers import IngredientSerializer

INGREDIENTS_URL = reverse('recipe:ingredient-list')


def detail_url(ingredient_id):
    """Create and return a ingredient detail url."""
    return reverse('recipe:ingredient-detail', args=[ingredient_id])


def create_user(email='user@exampl.com', pwd='password123'):
    """Create and return new user."""
    return get_user_model().objects.create_user(email, pwd)  # type: ignore


class PublicIngredientsApiTests(TestCase):
    """Tests unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth required to call API."""
        res = self.client.get(INGREDIENTS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredirentsAPITests(TestCase):
    """Tests authenticated tags API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """Test retrieving a list of ingredients."""

        Ingredient.objects.create(user=self.user, name='Ingredient1')
        Ingredient.objects.create(user=self.user, name='Ingredient2')
        res = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore

    def test_ingredients_limited_to_user(self):
        """Test list of ingredients is limited to authenticated user."""
        user2 = create_user(email='user2@example.com')
        Ingredient.objects.create(user=user2, name='Salt')
        ingredient = Ingredient.objects.create(user=self.user, name='Papper')

        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)  # type: ignore
        self.assertEqual(res.data[0]['name'], ingredient.name)  # type: ignore
        self.assertEqual(res.data[0]['id'], ingredient.id)  # type: ignore

    def test_update_ingredient(self):
        """Test updating an ingredient."""
        ingredient = Ingredient.objects.create(user=self.user, name='Salt')
        payload = {'name': 'Sugar'}
        url = detail_url(ingredient.id)  # type: ignore
        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredient.refresh_from_db()

        self.assertEqual(ingredient.name, payload['name'])
        self.assertEqual(ingredient.user, self.user)

    def test_delete_ingredient(self):
        """Test deleting the ingredient."""
        ingredient = Ingredient.objects.create(user=self.user, name='Beef')

        url = detail_url(ingredient.id)  # type: ignore
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        ingerd = Ingredient.objects.filter(id=ingredient.id)  # type: ignore
        self.assertFalse(ingerd.exists())

    def test_filter_ingredients_assigned_to_recipes(self):
        """Test listing ingredients by those assigned to recipes."""
        ing1 = Ingredient.objects.create(user=self.user, name='Ingredients1')
        ing2 = Ingredient.objects.create(user=self.user, name='Ingredients2')
        recipe = Recipe.objects.create(
            user=self.user,
            title='Some recipe',
            time_minutes=5,
            price=Decimal('2.54'),
        )
        recipe.ingredients.add(ing1)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        s1 = IngredientSerializer(ing1)
        s2 = IngredientSerializer(ing2)

        self.assertIn(s1.data, res.data)  # type: ignore
        self.assertNotIn(s2.data, res.data)  # type: ignore

    def test_filtered_ingredients_unique(self):
        """Test filtered ingredients returns a unique list."""
        ing = Ingredient.objects.create(user=self.user, name='Eggs')
        Ingredient.objects.create(user=self.user, name='Lentils')
        recipe1 = Recipe.objects.create(
            title='Recipe1',
            time_minutes=20,
            price=Decimal('2.54'),
            user=self.user,
        )
        recipe2 = Recipe.objects.create(
            title='Recipe2',
            time_minutes=20,
            price=Decimal('2.54'),
            user=self.user,
        )
        recipe1.ingredients.add(ing)
        recipe2.ingredients.add(ing)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)  # type: ignore
