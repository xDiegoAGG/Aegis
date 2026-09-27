import boto3
import random

dynamodb = boto3.resource("dynamodb",
    endpoint_url="http://localhost:8000",
    region_name="us-east-1",
    aws_access_key_id="local",
    aws_secret_access_key="local",
)

TABLE_NAME = "tb_books"

# Crear la tabla si no existe
existing_tables = []
for dynamodb_table in dynamodb.tables.all():
    existing_tables.append(dynamodb_table.name)

if TABLE_NAME not in existing_tables:
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Tabla '{TABLE_NAME}' creada.")
else:
    table = dynamodb.Table(TABLE_NAME)
    print(f"Tabla '{TABLE_NAME}' ya existía.")

# Libros original de la app mybookstore

libros_originales = [
    {
        "id": "1", "name": "Cumbres Borrascosas", "author": "Emily Brontë",
        "description": "Esta edición de Cumbres Borrascosas forma parte de la colección Jardín Secreto de Editorial Alma, caracterizada por libros de tapa dura con un diseño estético y detallado. La obra de Emily Brontë narra la intensa y oscura historia de amor, venganza y obsesión entre Catherine Earnshaw y Heatcliff en los páramos de Yorkshire.",
        "price": 183754, "countInStock": 3, "image": "/images/img-cumbres-borrascosas.jpeg",
    },
    {
        "id": "2", "name": "Como agua para chocolate", "author": "Laura Esquivel",
        "description": "Tita y Pedro se aman. Pero ella está condenada a permanecer soltera, cuidando a su madre hasta que ésta muera. Y Pedro, para estar cerca de Tita, se casa con la hermana de ella, Rosaura. Las recetas de cocina que Tita elabora, además de construir narrativamente la novela, puntean el paso de las estaciones de su vida.",
        "price": 63200, "countInStock": 12, "image": "/images/img-como-agua-para-chocolate.jpeg",
    },
    {
        "id": "3", "name": "Orgullo y Prejuicio", "author": "Jane Austen",
        "description": "Orgullo y prejuicio narra cómo Elizabeth Bennet y Fitzwilliam Darcy se enfrentan a sus prejuicios movidos por el amor que, contra pronóstico, surge entre ellos.",
        "price": 280363, "countInStock": 1, "image": "/images/img-orgullo-y-prejuicio.jpeg",
    },
    {
        "id": "4", "name": "Jane Eyre", "author": "Charlotte Brontë",
        "description": "Jane Eyre es una novela clásica de la literatura inglesa, considerada una de las primeras obras en explorar la psicología profunda de una protagonista femenina y un referente del feminismo temprano.",
        "price": 134250, "countInStock": 10, "image": "/images/img-Jane-Eyre.jpeg",
    },
    {
        "id": "5", "name": "En agosto nos vemos", "author": "Gabriel García Márquez",
        "description": "Novela póstuma de Gabriel García Márquez, centrada en Ana Magdalena Bach, quien cada 16 de agosto viaja a una isla del Caribe para visitar la tumba de su madre.",
        "price": 57600, "countInStock": 8, "image": "/images/img-en-agosto-nos-vemos.jpeg",
    },
    {
        "id": "6", "name": "El gran Gatsby", "author": "F. Scott Fitzgerald",
        "description": "Ambientada en los locos años veinte, narra la historia del misterioso millonario Jay Gatsby y su obsesión por reconquistar a su antiguo amor, Daisy Buchanan.",
        "price": 57157, "countInStock": 5, "image": "/images/img-el-gran-gatsby.jpeg",
    },
]

for libro in libros_originales:
    table.put_item(Item=libro)
print(f"Sembrados {len(libros_originales)} libros originales.")

# Libros adicionales para que el Scan tenga peso real bajo carga

autores = ["Gabriel García Márquez", "Isabel Allende", "Jorge Luis Borges", "Julio Cortázar", "Mario Vargas Llosa"]
for i in range(7, 51):
    table.put_item(
        Item={
            "id": str(i),
            "name": f"Libro de prueba #{i}",
            "author": random.choice(autores),
            "description": "Descripción generada para pruebas de carga de Aegis.",
            "price": random.randint(10000, 80000),
            "countInStock": random.randint(0, 100),
            "image": "https://via.placeholder.com/150",
        }
    )
    
print("Tabla de libros poblada completamente, estamos melos")