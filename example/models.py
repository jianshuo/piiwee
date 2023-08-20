from peewee import (
    MySQLDatabase,
    AutoField,
    CharField,
    DecimalField,
    DateField,
    TextField,
    ForeignKeyField,
    IntegerField,
    CompositeKey,
)

import piiwee

database = MySQLDatabase(
    "classicmodels",
    **{
        "charset": "utf8",
        "sql_mode": "PIPES_AS_CONCAT",
        "use_unicode": True,
        "user": "root",
    }
)


class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(piiwee.BaseModel):
    class Meta:
        database = database


class Offices(BaseModel):
    address_line1 = CharField(column_name="addressLine1")
    address_line2 = CharField(column_name="addressLine2", null=True)
    city = CharField()
    country = CharField()
    office_code = CharField(column_name="officeCode", primary_key=True)
    phone = CharField()
    postal_code = CharField(column_name="postalCode")
    state = CharField(null=True)
    territory = CharField()

    class Meta:
        table_name = "offices"


class Employees(BaseModel):
    email = CharField(_hidden=0o400)
    employee_number = AutoField(column_name="employeeNumber")
    extension = CharField()
    first_name = CharField(column_name="firstName")
    job_title = CharField(column_name="jobTitle")
    last_name = CharField(column_name="lastName")
    office_code = ForeignKeyField(
        column_name="officeCode",
        field="office_code",
        model=Offices,
        backref="employees",
    )
    reports_to = ForeignKeyField(
        column_name="reportsTo",
        field="employee_number",
        model="self",
        null=True,
        backref="subordinates",
    )

    class Meta:
        table_name = "employees"

    def get_role(self, user_id):
        return 0o700 if user_id == self.employee_number else 0o007


class Customers(BaseModel):
    address_line1 = CharField(column_name="addressLine1", _hidden=0o600)
    address_line2 = CharField(column_name="addressLine2", null=True, _hidden=0o600)
    city = CharField()
    contact_first_name = CharField(column_name="contactFirstName", _hidden=0o600)
    contact_last_name = CharField(column_name="contactLastName", _hidden=0o600)
    country = CharField()
    credit_limit = DecimalField(column_name="creditLimit", null=True, _hidden=0o404)
    customer_name = CharField(column_name="customerName", _hidden=0o600)
    customer_number = AutoField(column_name="customerNumber")
    phone = CharField(_hidden=0o600)
    postal_code = CharField(column_name="postalCode", null=True)
    sales_rep_employee_number = ForeignKeyField(
        column_name="salesRepEmployeeNumber",
        field="employee_number",
        model=Employees,
        null=True,
        backref="customers",
    )
    state = CharField(null=True)

    class Meta:
        table_name = "customers"
        permission = 0o777

    def get_role(self, user_id):
        return 0o700 if user_id == 5 or user_id == self.customer_number else 0o007


class Orders(BaseModel):
    comments = TextField(null=True)
    customer_number = ForeignKeyField(
        column_name="customerNumber",
        field="customer_number",
        model=Customers,
        backref="orders",
    )
    order_date = DateField(column_name="orderDate")
    order_number = AutoField(column_name="orderNumber")
    required_date = DateField(column_name="requiredDate")
    shipped_date = DateField(column_name="shippedDate", null=True)
    status = CharField()

    class Meta:
        table_name = "orders"


class Productlines(BaseModel):
    html_description = TextField(column_name="htmlDescription", null=True)
    image = TextField(null=True)
    product_line = CharField(column_name="productLine", primary_key=True)
    text_description = CharField(column_name="textDescription", null=True)

    class Meta:
        table_name = "productlines"


class Products(BaseModel):
    msrp = DecimalField(column_name="MSRP")
    buy_price = DecimalField(column_name="buyPrice")
    product_code = CharField(column_name="productCode", primary_key=True)
    product_description = TextField(column_name="productDescription")
    product_line = ForeignKeyField(
        column_name="productLine",
        field="product_line",
        model=Productlines,
        backref="productlines",
    )
    product_name = CharField(column_name="productName")
    product_scale = CharField(column_name="productScale")
    product_vendor = CharField(column_name="productVendor")
    quantity_in_stock = IntegerField(column_name="quantityInStock")

    class Meta:
        table_name = "products"


class Orderdetails(BaseModel):
    order_line_number = IntegerField(column_name="orderLineNumber")
    order_number = ForeignKeyField(
        column_name="orderNumber", field="order_number", model=Orders, backref="details"
    )
    price_each = DecimalField(column_name="priceEach")
    product_code = ForeignKeyField(
        column_name="productCode",
        field="product_code",
        model=Products,
        backref="products",
    )
    quantity_ordered = IntegerField(column_name="quantityOrdered")

    class Meta:
        table_name = "orderdetails"
        indexes = ((("order_number", "product_code"), True),)
        primary_key = CompositeKey("order_number", "product_code")


class Payments(BaseModel):
    amount = DecimalField()
    check_number = CharField(column_name="checkNumber")
    customer_number = ForeignKeyField(
        column_name="customerNumber",
        field="customer_number",
        model=Customers,
        backref="payments",
    )
    payment_date = DateField(column_name="paymentDate")

    class Meta:
        table_name = "payments"
        indexes = ((("customer_number", "check_number"), True),)
        primary_key = CompositeKey("check_number", "customer_number")
