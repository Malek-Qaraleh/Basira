from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from core.models import ScrapeBatch, ScrapeJob, Product, Site

class BasiraBackendTests(TestCase):
    def setUp(self):
        # Setup common data for all tests
        self.user = User.objects.create_user(username='firas_tester', password='password123')
        self.client = Client()
        self.client.login(username='firas_tester', password='password123')
        self.scrape_url = reverse('scrape')

    def test_01_scrape_flow_logic(self):
        """TEST CASE 1: Verifies that form submission creates Batch and Job objects"""
        payload = {
            'category_url': 'https://www.dumyah.com/en/toys',
            'max_items': 10,
            'max_pages': 1,
            'pagination_type': 'auto',
            'fields': ['title', 'price']
        }
        
        self.client.post(self.scrape_url, data=payload)

        # --- CONSOLE REPORT FOR DOCUMENTATION ---
        print("\n" + "="*50)
        print("TEST CASE 01: SCRAPE FLOW VERIFICATION")
        print("="*50)
        batch = ScrapeBatch.objects.first()
        if batch:
            print(f"STATUS:    SUCCESS")
            print(f"USER:      {self.user.username}")
            print(f"BATCH ID:  {batch.id}")
            print(f"QUERY URL: {batch.query}")
            print(f"JOB TYPE:  {batch.scrapejob_set.first().site}")
        else:
            print("STATUS:    FAILED - NO BATCH CREATED")
        print("="*50 + "\n")

        self.assertEqual(ScrapeBatch.objects.count(), 1)
        self.assertEqual(ScrapeJob.objects.count(), 1)

    def test_02_product_data_integrity(self):
        """TEST CASE 2: Verifies that scraped products are saved with correct price logic"""
        # Create parents
        batch = ScrapeBatch.objects.create(user=self.user, query="Manual Test")
        job = ScrapeJob.objects.create(batch=batch, site=Site.DUMYAH)

        # Create Product with specific data
        test_price = Decimal('45.99')
        Product.objects.create(
            job=job,
            site=Site.DUMYAH,
            title="Educational Robot Toy",
            price=test_price,
            currency="JOD",
            product_url="https://dumyah.com/robot"
        )

        # --- CONSOLE REPORT FOR DOCUMENTATION ---
        print("\n" + "="*50)
        print("TEST CASE 02: PRODUCT DATA INTEGRITY")
        print("="*50)
        prod = Product.objects.first()
        print(f"PRODUCT:   {prod.title}")
        print(f"DB PRICE:  {prod.price} {prod.currency}")
        print(f"DATA TYPE: {type(prod.price)}")
        print(f"SITE TAG:  {prod.site}")
        print(f"RELATION:  Linked to Job ID {prod.job.id}")
        print("="*50 + "\n")

        self.assertEqual(Product.objects.count(), 1)
        # Verify the price is stored as a numerical type (Decimal or Float)
        self.assertIsInstance(prod.price, (Decimal, float))