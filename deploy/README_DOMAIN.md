# Configuracion del dominio memedetector.es

## Contexto

El dashboard de Streamlit se despliega en **Render** y queda accesible en:

```
https://www.memedetector.es
```

El dominio apex (`memedetector.es`, sin www) esta alojado en **cPanel** (plames). Render no puede gestionar dominios apex directamente a menos que el proveedor DNS soporte registros ALIAS/ANAME, cosa que cPanel no hace.

La solucion es crear un archivo `.htaccess` en cPanel que redirija todo el trafico de `memedetector.es` hacia `www.memedetector.es` (que apunta a Render).

---

## Instrucciones paso a paso

### 1. Acceder a cPanel

Entra en el panel de control de tu hosting:

```
https://tu-hosting.com/cpanel   (o la URL que te proporcione tu proveedor)
```

Usa tus credenciales de la cuenta `plames`.

### 2. Abrir el Administrador de Archivos

- En el panel principal de cPanel, busca **"Administrador de archivos"** (o "File Manager" si esta en ingles).
- Haz clic para abrirlo.

### 3. Navegar a la carpeta del dominio

En el arbol de directorios de la izquierda, navega hasta:

```
/home/plames/memedetector.es/
```

### 4. Crear el archivo .htaccess

**Opcion A: Crear archivo nuevo**

1. En la barra superior, haz clic en **"+ Archivo"** (o "+ File").
2. Nombre del archivo: `.htaccess` (con el punto delante, es importante).
3. Ubicacion: `/home/plames/memedetector.es/`
4. Haz clic en **"Create New File"**.

**Opcion B: Subir archivo existente**

1. En la barra superior, haz clic en **"Subir"** (o "Upload").
2. Sube el archivo `htaccess_memedetector` que esta en la carpeta `deploy/` de este proyecto.
3. Una vez subido, renombralo a `.htaccess`.

### 5. Pegar el contenido

Si elegiste la Opcion A, haz doble clic (o clic derecho > "Edit") sobre el archivo `.htaccess` recien creado y pega este contenido:

```apache
RewriteEngine On
RewriteCond %{HTTP_HOST} ^memedetector\.es$ [NC]
RewriteRule ^(.*)$ https://www.memedetector.es/$1 [R=301,L]
```

Guarda el archivo (boton "Save Changes" arriba a la derecha).

### 6. Verificar que funciona

Desde tu terminal, ejecuta:

```bash
curl -I http://memedetector.es
```

Deberias ver una respuesta con:

```
HTTP/1.1 301 Moved Permanently
Location: https://www.memedetector.es/
```

Tambien puedes abrir `http://memedetector.es` en el navegador y comprobar que redirige automaticamente a `https://www.memedetector.es`.

---

## Nota sobre visibilidad de archivos ocultos en cPanel

Si no ves el archivo `.htaccess` despues de crearlo, activa la opcion de mostrar archivos ocultos:

1. En el Administrador de Archivos, haz clic en **"Configuracion"** (icono de engranaje, arriba a la derecha).
2. Marca la casilla **"Mostrar archivos ocultos (dotfiles)"**.
3. Haz clic en **"Save"**.

---

## Resumen de la arquitectura DNS

```
memedetector.es (apex)
  └── cPanel (.htaccess) ── 301 redirect ──> www.memedetector.es

www.memedetector.es
  └── CNAME ──> Render (dashboard Streamlit)
```

## Archivos relacionados

| Archivo | Descripcion |
|---------|-------------|
| `deploy/htaccess_memedetector` | Contenido del .htaccess listo para subir |
| `deploy/README_DOMAIN.md` | Este archivo de instrucciones |
| `render.yaml` | Blueprint de Render para el servicio web |
