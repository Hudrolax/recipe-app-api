"""
Tests for recipe APIs.
"""
from decimal import Decimal
import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient
from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer,
)

RECIPES_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def image_upload_url(recipe_id):
    """Create and return an image upload URL."""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a simple recipe"""
    defaults = {
        'title': 'Simple recipe title.',
        'time_minutes': 22,
        'price': Decimal('5.25'),
        'description': 'Sample description',
        'link': 'http://example.com/recipe.pdf',
    }
    defaults.update(**params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


def create_user(**params):
    """Create and return new user."""
    return get_user_model().objects.create_user(**params)  # type: ignore


class PublicRecipeAPITests(TestCase):
    """Tests for unautheticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth required to call API."""
        res = self.client.get(RECIPES_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Tests authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email='user@example.com', password='testpas14')
        self.client.force_authenticate(self.user)

    def test_retrieve_recipies(self):
        """Test retieving a list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is limited to authenticated user."""
        other_user = create_user(email='other@example.com',
                                 password='otherpassword1234')

        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  #type: ignore

    def test_get_recipe_detail(self):
        """Test get recipe detail."""
        recipe = create_recipe(self.user)

        url = detail_url(recipe.id)  # type: ignore
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)  # type: ignore

    def test_create_recipe(self):
        """Test create a recipe."""
        payload = {
            'title': 'Simple recipe',
            'time_minutes': 30,
            'price': Decimal('5.99'),
        }
        res = self.client.post(RECIPES_URL, payload)  # /api/recipes/recipe

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])  # type: ignore
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """Test partial uptade of a recipe."""
        original_link = 'https://example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user,
            title='Simple recipe title',
            link=original_link,
        )
        payload = {'title': 'New recipe title'}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        """Test full update of recipe."""
        recipe = create_recipe(
            user=self.user,
            title='Simple recipe title',
            link='https://example.com/recipe.pdf',
            description='Sample recipe descriprion',
        )
        payload = {
            'title': 'New recipe title',
            'link': 'https://example.com/new-recipe.pdf',
            'description': 'New recipe description',
            'time_minutes': 10,
            'price': Decimal('2.50'),
        }
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.put(url, payload)  # put for full update
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_update_user_returns_error(self):
        """Test changing the recipe user results in an error."""
        new_user = create_user(email='user2@example.com', password='user123')
        recipe = create_recipe(user=self.user)
        payload = {'user': new_user.id}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload)
        recipe.refresh_from_db()

        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Test deliting a recipe successful."""
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Recipe.objects.filter(id=recipe.id).exists())  # type: ignore

    def test_delete_recipe_other_users_recipe_error(self):
        """Test trying to delete another users recipe gives error."""
        new_user = create_user(email='user2@example.com', password='user123')
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)  # type: ignore
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Recipe.objects.filter(id=recipe.id).exists())  # type: ignore

    def test_create_recipe_with_new_tag(self):
        """Test creating a new recipe with a new tag."""
        payload = {
            'title': 'Simple recipe title',
            'time_minutes': 20,
            'price': Decimal('2.50'),
            'tags': [{
                'name': 'Thai'
            }, {
                'name': 'Dinner'
            }],
        }
        # format = 'json' потому, что в payload сложный объект.
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)  # type: ignore
        for tag in payload['tags']:
            exist = Tag.objects.filter(
                user=self.user,
                name=tag['name'],
            ).exists()
            self.assertTrue(exist)

    def test_create_recipe_with_existing_tag(self):
        """Test creating a recipe with existing tag."""
        tag = Tag.objects.create(user=self.user, name='Dinner')
        payload = {
            'title': 'Simple recipe title',
            'time_minutes': 20,
            'price': Decimal('2.50'),
            'tags': [{
                'name': 'Thai'
            }, {
                'name': 'Dinner'
            }],
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)  # type: ignore
        self.assertIn(tag, recipe.tags.all())  # type: ignore
        for tag in payload['tags']:
            exist = Tag.objects.filter(
                user=self.user,
                name=tag['name'],
            ).exists()
            self.assertTrue(exist)

    def test_create_tag_on_update(self):
        """Test creating a new tag on updating a recipe."""
        recipe = create_recipe(user=self.user)

        payload = {'tags': [{'name': 'Lunch'}]}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='Lunch')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe."""
        tag_breakfast = Tag.objects.create(user=self.user, name='Breakfast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name='Lunch')
        payload = {'tags': [{'name': 'Lunch'}]}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing a recipe tags."""
        tag1 = Tag.objects.create(user=self.user, name='Tag1')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag1)

        payload = {'tags': []}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a new recipe with new ingredients."""
        payload = {
            'title': 'Simple recipe title',
            'time_minutes': 20,
            'price': Decimal('2.50'),
            'ingredients': [{
                'name': 'Salt'
            }, {
                'name': 'Sugar'
            }],
        }
        # format = 'json' потому, что в payload сложный объект.
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)  # type: ignore
        for ingredient in payload['ingredients']:
            exist = Ingredient.objects.filter(
                user=self.user,
                name=ingredient['name'],
            ).exists()
            self.assertTrue(exist)

    def test_create_recipe_with_existing_ingredient(self):
        """Test creating a new recipe with exisiting ingredient."""
        ingredient = Ingredient.objects.create(user=self.user, name='Lemon')
        payload = {
            'title': 'Simple recipe title',
            'time_minutes': 20,
            'price': Decimal('2.50'),
            'ingredients': [{
                'name': 'Lemon'
            }, {
                'name': 'Sugar'
            }],
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)  # type: ignore
        self.assertIn(ingredient, recipe.ingredients.all())  # type: ignore
        for ingredient in payload['ingredients']:
            exist = recipe.ingredients.filter(  # type: ignore
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exist)

    def test_create_ingredient_on_update(self):
        """Test creating an ingredient when updating a recipe."""
        recipe = create_recipe(user=self.user)

        payload = {'ingredients': [{'name': 'Salt'}]}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(user=self.user, name='Salt')
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assigning an exisiting ingredient when updating a recipe."""
        ingredient1 = Ingredient.objects.create(user=self.user, name='Papper')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)
        ingredient2 = Ingredient.objects.create(user=self.user, name='Water')
        payload = {'ingredients': [{'name': 'Water'}]}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingrediants(self):
        """Test clearing a recipe ingredients."""
        ingredient = Ingredient.objects.create(user=self.user, name='Salt')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {'ingredients': []}
        url = detail_url(recipe.id)  # type: ignore
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_tags(self):
        """Test filtering recipes by tags."""
        r1 = create_recipe(user=self.user, title='Recipe1')
        r2 = create_recipe(user=self.user, title='Recipe2')
        tag1 = Tag.objects.create(user=self.user, name='Tag1')
        tag2 = Tag.objects.create(user=self.user, name='Tag2')
        r1.tags.add(tag1)
        r2.tags.add(tag2)
        r3 = create_recipe(user=self.user, title='Recipe3')

        params = {'tags': f'{tag1.id},{tag2.id}'}  # type: ignore
        res = self.client.get(RECIPES_URL, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)

        self.assertIn(s1.data, res.data)  # type: ignore
        self.assertIn(s2.data, res.data)  # type: ignore
        self.assertNotIn(s3.data, res.data)  # type: ignore

    def test_filter_by_ingredients(self):
        """Test filtering recipes by ingredients."""
        r1 = create_recipe(user=self.user, title='Recipe1')
        r2 = create_recipe(user=self.user, title='Recipe2')
        in1 = Ingredient.objects.create(user=self.user, name='Ingredient1')
        in2 = Ingredient.objects.create(user=self.user, name='Ingredient2')
        r1.ingredients.add(in1)
        r2.ingredients.add(in2)
        r3 = create_recipe(user=self.user, title='Recipe3')

        params = {'ingredients': f'{in1.id},{in2.id}'}  # type: ignore
        res = self.client.get(RECIPES_URL, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)

        self.assertIn(s1.data, res.data)  # type: ignore
        self.assertIn(s2.data, res.data)  # type: ignore
        self.assertNotIn(s3.data, res.data)  # type: ignore


class ImageUploadTests(TestCase):
    """Tests for image upload API."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create(
            email='user@example.com',
            password='test12345',
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """Test upload image to a recipe."""
        url = image_upload_url(self.recipe.id)  # type: ignore
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {'image': image_file}
            res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.recipe.refresh_from_db()
        self.assertIn('image', res.data)  # type: ignore
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bed_request(self):
        """Test uploading invilid image."""
        url = image_upload_url(self.recipe.id)  # type: ignore
        payload = {'image': "not_image"}
        res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
