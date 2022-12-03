"""
Tests for the tags API.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core import models

from recipe.serializers import TagSerializer

TAGS_URL = reverse('recipe:tag-list')


def detail_url(tag_id):
    """Create and return a tag detail url."""
    return reverse('recipe:tag-detail', args=[tag_id])


def create_user(email='user@exampl.com', pwd='password123'):
    """Create and return new user."""
    return get_user_model().objects.create_user(email, pwd)  # type: ignore


class PublicTagsApiTests(TestCase):
    """Tests unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth required to call API."""
        res = self.client.get(TAGS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTagsAPITests(TestCase):
    """Tests authenticated tags API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Test retieving a list of tags."""

        models.Tag.objects.create(user=self.user, name='Vegan')
        models.Tag.objects.create(user=self.user, name='Dessert')
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        tags = models.Tag.objects.all().order_by('-name')
        serializer = TagSerializer(tags, many=True)

        self.assertEqual(res.data, serializer.data)  # type: ignore

    def test_tags_list_limited_to_user(self):
        """Test list of tags is limited th authenticated user."""
        other_user = create_user(email='other@example.com',
                                 pwd='otherpassword1234')
        models.Tag.objects.create(user=other_user, name='Vegan')
        models.Tag.objects.create(user=self.user, name='Dessert')

        res = self.client.get(TAGS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tags = models.Tag.objects.filter(user=self.user)
        serializer = TagSerializer(tags, many=True)
        self.assertEqual(res.data, serializer.data)  # type: ignore

    def test_update_tag(self):
        """Test updating the tag."""
        tag = models.Tag.objects.create(user=self.user, name='After dinner')
        payload = {'name': 'Dessert'}

        url = detail_url(tag.id)  # type: ignore
        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tag.refresh_from_db()

        self.assertEqual(tag.name, payload['name'])  # type: ignore
        self.assertEqual(tag.user, self.user)

    def test_delete_tag(self):
        """Test deleting the tag."""
        tag = models.Tag.objects.create(user=self.user, name='After dinner')

        url = detail_url(tag.id)  # type: ignore
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Tag.objects.filter(id=tag.id).exists())
