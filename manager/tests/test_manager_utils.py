from django.test import TestCase
from manager.utils.category_handler import (CategoryHandlerFactory, GeneralQueueHandler, RestaurantQueueHandler,
                                            BankQueueHandler, HospitalQueueHandler)


class CategoryHandlerFactoryTest(TestCase):
    def test_factory_returns_general_handler(self):
        handler = CategoryHandlerFactory.get_handler('general')
        self.assertIsInstance(handler, GeneralQueueHandler)

    def test_factory_returns_restaurant_handler(self):
        handler = CategoryHandlerFactory.get_handler('restaurant')
        self.assertIsInstance(handler, RestaurantQueueHandler)

    def test_factory_returns_bank_handler(self):
        handler = CategoryHandlerFactory.get_handler('bank')
        self.assertIsInstance(handler, BankQueueHandler)

    def test_factory_returns_hospital_handler(self):
        handler = CategoryHandlerFactory.get_handler('hospital')
        self.assertIsInstance(handler, HospitalQueueHandler)

    def test_factory_caches_handlers(self):
        handler1 = CategoryHandlerFactory.get_handler('general')
        handler2 = CategoryHandlerFactory.get_handler('general')
        self.assertIs(handler1, handler2)

