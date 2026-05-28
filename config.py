import psycopg2

def get_connection():
    try:
        connection = psycopg2.connect(
            user="postgres",           
            password="Pumanegro2005**", 
            host="127.0.0.1",          
            port="5432",
            database="Inventario_proyecto"     
        )
        connection.set_client_encoding('UTF8') 
        return connection
    except Exception as e:
        print("Error: No se pudo conectar a PostgreSQL. Revisa usuario y contraseña.")
        return None