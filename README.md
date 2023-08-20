# piiwee

Adding Caching, Permission Control, Graph REST API to Peewee ORM.

Peewee is a great ORM, and FastAPI is a great web framework. However, there
is a gap between them. Thousands of developers write their own caching,
permission control, and biuld RESTful API for frontend.

## Features

- Cache support. It support both single query result (like `/customers/3`),
  and SELECT query results (like `/customers/?filter=customer_num==1024`)
- A simple in-memory cache store is included, and can be replaced by Redis
- Model level and field level permission control for READ and WRITE.
- Leveraged Unix style `rwxrwxrwx` for setting different permission for `OWNER`,
  `GROUP`, and `OTHER`. For example, we can easily control only `OWNER` can see certain
  fields, while they can only `READ` but not `WRITE` certain fields.
- Mapping between query parameters (like filter, sort, fields) to Peewee
  Expression, handy to build RESTful API.

## Usage

Install with PIP:

> pip install piiwee

After that, the only thing you need to do is to replace `Model` with `piiwee.BaseModel`
in your model definitation files, then all your models automatically has all the
features outlined above.

## Run Sample Server

You can setup a MySQL with ClassicModel sample dataset (https://www.mysqltutorial.org/mysql-sample-database.aspx). The database configuration is in `models.py`. You can go to `example` folder and run

> python main.py

Visit `https://127.0.0.1:8000/customers` to try it out.

## Cache

Out of box, the cache is handled by MemoryStore - a dict stored in the memory of the
server running the code. You can monitor the cache HIT or MISS by config the logging
level to DEBUG

> logging.basicConfig(level=logging.DEBUG)

You can use your own REDIS server to replace the in-memory caching.

> BaseModel.set_store(Redis())

## Permissions

In your Model definition, you can define permissions at model level or field level.

### Model Level

      >>> from peewee import CharField
      >>> class User(Model):
      ...     class Meta:
      ...         permission = 0o604
      >>> oct(User().model_perm())
      '0o604'

0o604 follows Unix style to specify READ and WRITE for OWNER, and READ only for others.

### Field Level

To avoid bigger change, we just leverage a pre-defined \_hidden field of Field to set
permission for that specific field. The rule is the same as model level permissions.
The final permission is bitwise AND between the model level and field level permissions.

      >>> from peewee import CharField
      >>> class User(Model):
      ...     name = CharField(max_length=100, _hidden=0o604)
      ...     mobile = CharField(max_length=100, _hidden=0o600)
      ...     role = CharField(max_length=100, _hidden=0o404)
      ...     class Meta:
      ...         permission = 0o600

      >>> oct(User.field_perm(User.name))
      '0o600'

      >>> oct(User().model_perm())
      '0o604'

      >>> User.field_perms()
      {<AutoField: User.id>: 384, <CharField: User.name>: 384, <CharField: User.mobile>: 384, <CharField: User.role>: 256}

## RESTful API

Please refer to `main.py` in `example` folder for a simple demo. It provides several
RESTful endpoints:

### GET /{kind}/{id}

Get the specific object of that kind

### GET /{kind}/

List items of that type of object. The following query parameters can be used:

- `sort`. Sort the result by the fields. A `-` means descendant.
- `filter`. Filter the result. You can provide any PYTHON style query like: `filter=customer_number<230+and+customer_number>200+and+country=="UK"`. Please NOTE:
  `equal` must use `==` and string needs to be quoted (single or double quotes are OK)
- `fields`. Only returns fields specified.
- `page` and `size`. These are for paging

### GET /{kind}/{id}/{backrefs}

This leverage backrefs of Peewee to build connections between objects. For example:

`/offices/3/employees` list all the `employees` working in `office` `3`.

### POST /{kind}/{id}

Update the object. Permission control is enforced
