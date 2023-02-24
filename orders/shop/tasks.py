import yaml
from django.conf.global_settings import EMAIL_HOST_USER
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail.message import EmailMultiAlternatives
from django.db import transaction

from orders.celery import app
from .models import Category, Parameter, ProductParameter, Product, Shop, ProductInfo


@app.task()
def send_email(message: str, email: str, *args, **kwargs) -> str:
    title = 'Title'
    email_list = list()
    email_list.append(email)
    try:
        msg = EmailMultiAlternatives(subject=title, body=message, from_email=EMAIL_HOST_USER, to=email_list)
        msg.send()
        return f'Title: {msg.subject}, Message:{msg.body}'
    except Exception as e:
        raise e


def open_file(shop: InMemoryUploadedFile):
    with shop.open('r') as f:
        data = yaml.safe_load(f)
    return data


@app.task()
def import_shop_data(data, user_id):
    # TODO: проверить что за херня (Product vs ProductInfo)
    file = open_file(data)

    with transaction.atomic():
        shop, _ = Shop.objects.get_or_create(
            user_id=user_id,
            defaults={'name': file['shop']}
        )

        Category.objects.bulk_create([
            Category(id=category['id'], name=category['name'])
            for category in file['categories']
        ])

        Product.objects.filter(product_infos__shop_id=shop.id).delete()

        products_to_insert = []
        product_infos_to_insert = []
        product_parameters_to_insert = []

        for item in file['goods']:
            product = Product(
                name=item['name'],
                category_id=item['category'],
            )
            products_to_insert.append(product)

            product_info = ProductInfo(
                model=item['model'],
                quantity=item['quantity'],
                price=item['price'],
                price_rrc=item['price_rrc'],
                product=product,
                shop=shop,
            )
            product_infos_to_insert.append(product_info)

            for name, value in item['parameters'].items():
                parameter, _ = Parameter.objects.get_or_create(name=name)
                product_parameter = ProductParameter(
                    product_info=product_info,
                    parameter=parameter,
                    value=value
                )
                product_parameters_to_insert.append(product_parameter)

        Product.objects.bulk_create(products_to_insert)
        ProductInfo.objects.bulk_create(product_infos_to_insert)
        ProductParameter.objects.bulk_create(product_parameters_to_insert)
