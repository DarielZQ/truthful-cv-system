# Guía de uso en Windows

Esta guía explica cómo instalar, configurar y operar **Truthful CV System** sin publicar datos privados. Los comandos están escritos para PowerShell y deben ejecutarse desde la raíz del repositorio, salvo que se indique lo contrario.

> [!IMPORTANT]
> El repositorio contiene código y ejemplos sintéticos. Los datos reales deben permanecer en `profile/private/`, `private/`, `generated/` y `deliverables/`, que Git ignora. Nunca confirme contraseñas, tokens, documentos fuente ni datos personales en Git.

## Etapa 1: entender qué hace el programa

El sistema mantiene un perfil profesional estructurado, vincula afirmaciones a fuentes, impide exportar contenido no aprobado, evalúa requisitos laborales mediante etiquetas y genera YAML para RenderCV. Después verifica que el PDF resultante:

- tenga una capa de texto legible;
- no exceda el límite de páginas;
- no contenga expresiones prohibidas;
- incluya el inventario de texto esperado;
- provenga de líneas aprobadas mediante firmas exactas.

RenderCV solo presenta el contenido. El perfil y el manifiesto privados son la fuente de verdad. El programa no envía solicitudes de empleo.

**Resultado esperado:** puede explicar que el flujo es `fuentes → perfil → manifiesto aprobado → YAML → PDF → verificación`.

## Etapa 2: conocer las carpetas y archivos

| Ruta | Contenido |
|---|---|
| `src/truthful_cv/` | Código de validación, coincidencia, adaptación a RenderCV, verificación y seguimiento. |
| `tests/` | Pruebas automatizadas con datos sintéticos. |
| `samples/` | Perfil, fuentes, manifiesto y escenarios de coincidencia completamente sintéticos. |
| `profile/README.md` | Regla de almacenamiento para perfiles. |
| `profile/private/` | Perfil, fuentes y manifiestos reales; está ignorado por Git. |
| `private/` | Investigación, capturas y registros privados; está ignorado por Git. |
| `generated/` | YAML y archivos generados; solo `.gitkeep` pertenece al repositorio. |
| `deliverables/` | PDFs finales privados; está ignorado por Git. |
| `docs/` | Arquitectura, esquema, seguridad y decisiones. |
| `pyproject.toml` | Dependencias, versión mínima de Python y comandos del paquete. |
| `uv.lock` | Versiones resueltas para instalaciones reproducibles. |
| `.gitignore` | Barrera contra datos privados, credenciales y artefactos locales. |

**Resultado esperado:** `git status --short` no debe mostrar archivos guardados en rutas privadas ignoradas.

## Etapa 3: instalar los requisitos

Necesita:

1. Windows 10 u 11.
2. Git para clonar y actualizar el repositorio.
3. `uv` para administrar Python y las dependencias.
4. Acceso autorizado al repositorio privado.

El proyecto declara Python `>=3.13` y fija `.python-version` en `3.14.3`. `uv` puede instalar la versión administrada necesaria durante la sincronización. RenderCV `2.8` se instala mediante el extra `render`; pytest y Ruff, mediante `dev`.

Compruebe las herramientas:

```powershell
git --version
uv --version
```

Si falta alguna, instálela desde sus instrucciones oficiales y abra una nueva terminal.

**Resultado esperado:** ambos comandos imprimen una versión y terminan sin error.

## Etapa 4: clonar o descargar el repositorio

Método recomendado:

```powershell
git clone <URL_PRIVADA_DEL_REPOSITORIO>
Set-Location truthful-cv-system
```

Para una descarga ZIP, use la interfaz web autorizada, extraiga el archivo y abra PowerShell dentro de la carpeta. El método ZIP no conserva el historial ni permite `git pull`.

Compruebe la raíz:

```powershell
git status --short --branch
```

**Resultado esperado:** al clonar, verá `## main...origin/main` y ningún archivo modificado.

## Etapa 5: instalar dependencias de forma segura

Desde la raíz:

```powershell
uv sync --extra dev --extra render --locked
```

`--locked` impide que la instalación cambie silenciosamente `uv.lock`. No instale paquetes del proyecto globalmente ni ejecute archivos descargados desde vacantes o currículos.

Compruebe la CLI:

```powershell
uv run truthful-cv --help
```

**Resultado esperado:** aparecen los comandos `validate-profile`, `build`, `verify-pdf` y `vacancy`.

## Etapa 6: configurar sin exponer secretos

Cree las carpetas privadas:

```powershell
New-Item -ItemType Directory -Force profile/private/manifests, generated, deliverables, private | Out-Null
```

Copie los ejemplos como punto de partida privado:

```powershell
Copy-Item samples/source-register.example.yaml profile/private/source-register.yaml
Copy-Item samples/profile.example.yaml profile/private/master-profile.yaml
Copy-Item samples/manifest.example.yaml profile/private/manifests/master.yaml
```

Antes de editar, confirme que Git los ignora:

```powershell
git check-ignore -v profile/private/master-profile.yaml
```

Nunca guarde tokens en YAML. Si una herramienta externa necesita autenticación, use su almacén seguro o flujo OAuth; `.env`, archivos de credenciales, claves y tokens están ignorados como defensa adicional, no como sustituto de un gestor de secretos.

**Resultado esperado:** `git check-ignore` muestra una regla de `.gitignore` para `profile/private/`.

## Etapa 7: definir los cuatro escenarios y sus reglas

`FitLevel` separa la recuperación automática de la decisión semántica:

1. **`absent`**: ninguna afirmación aprobada comparte etiquetas con el requisito.
2. **`partial`**: existen coincidencias de etiquetas; es una pista para revisión, no una prueba.
3. **`strong`**: una revisión humana confirmó evidencia suficiente y registró una justificación.
4. **`deep`**: una revisión humana confirmó evidencia amplia y registró una justificación.

Reglas adicionales:

- Solo cuentan afirmaciones con `status: approved`.
- La coincidencia automática de etiquetas no distingue mayúsculas de minúsculas y nunca
  produce por sí sola un nivel superior a `partial`.
- `strong` y `deep` requieren `override_level` y una explicación no vacía en
  `override_rationale`; aprobar la redacción de un requisito no aprueba automáticamente
  que el candidato lo cumpla.
- La cobertura de requisitos obligatorios pondera `deep` y `strong` como `1.0`, `partial` como `0.5` y `absent` como `0.0`.
- Un requisito con `hard_filter: true` falla si su resultado es `partial` o `absent`.
- El ejemplo declarativo está en `samples/job-requirements.example.yaml`.
- La coincidencia por etiquetas es una puntuación de recuperación; no es una prueba de que la persona cumpla el requisito. La revisión semántica humana sigue siendo obligatoria.

**Resultado esperado:** el archivo de ejemplo contiene exactamente `deep`, `strong`, `partial` y `absent`.

## Etapa 8: proporcionar datos sanitizados

Edite primero copias sintéticas. Mantenga estas reglas:

- Cada fuente tiene un ID único.
- Cada afirmación usa un ID `CLM-` con al menos tres dígitos.
- Las categorías permitidas son `professional`, `training`, `knowledge`, `education`, `language` y `certification`.
- Una afirmación aprobada necesita fuentes y no puede usar Tier D.
- Las fechas son un año de cuatro dígitos o `YYYY-MM` con mes `01` a `12`.
- Los roles usan `professional` o `structured_training`.
- No transforme cursos en certificaciones ni formación en empleo.
- No agregue métricas, responsabilidades o tecnologías que la evidencia no respalde.
- Use `summary_voice: first_person` cuando el resumen deba sonar como redactado por el
  candidato. En español use formas como `Soy`, `He trabajado` y `Tengo`, no `Ha trabajado`
  ni `Cuenta con`.

Después de revisar manualmente todas las líneas, vuelva a calcular las firmas exactas. El siguiente comando aprueba **todas** las líneas del manifiesto indicado; ejecútelo solo después de validar que cada una es verdadera y está correctamente vinculada:

```powershell
uv run python -c "from pathlib import Path; import yaml; from truthful_cv.profile import load_profile; from truthful_cv.manifest import load_manifest,line_signature; pp=Path('profile/private/master-profile.yaml'); sp=Path('profile/private/source-register.yaml'); mp=Path('profile/private/manifests/master.yaml'); p=load_profile(pp,sp); m=load_manifest(mp); d=yaml.safe_load(pp.read_text(encoding='utf-8')); d['approved_line_signatures']=[line_signature(x,p,m.language) for x in m.lines]; pp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True),encoding='utf-8')"
```

**Resultado esperado:** el perfil contiene una firma SHA-256 por línea aprobada y continúa fuera de `git status`.

## Etapa 9: ejecutar el programa

### Flujo Level-2 de una vacante

Ingrese una URL HTTPS elegida por usted:

```powershell
uv run truthful-cv vacancy ingest `
  --url "https://careers.example.com/jobs/42" `
  --private-root private `
  --title "Especialista de soporte" `
  --employer "Empresa Ejemplo"
```

LinkedIn, Indeed, Glassdoor, Workday y portales de Costa Rica siempre producen `paste_required` sin consultar la red. Las páginas arbitrarias de empleadores también requieren pegado salvo que usted haya verificado que la consulta anónima está permitida y agregue el host exacto con `--allow-public-host`. Solo las URL reconocidas de Greenhouse y Lever usan sus API públicas documentadas mediante GET. También se exige pegado ante inicio de sesión, consentimiento de cookies, CAPTCHA, Cloudflare, verificación humana, `403`, `429` o contenido incompleto. Copie únicamente el texto visible de la vacante a un archivo privado y reanude el mismo registro:

```powershell
uv run truthful-cv vacancy ingest `
  --url "https://www.linkedin.com/jobs/view/123" `
  --paste-file private/vacante-JOB-001.txt `
  --private-root private `
  --title "Especialista de soporte" `
  --employer "Empresa Ejemplo" `
  --location "Costa Rica" `
  --external-id "123"
```

**Salidas esperadas:** `paste_required: JOB-001` si debe pegar el texto, o `requirements_review: JOB-001` cuando existen `private/vacancies/JOB-001/snapshot.yaml` y `requirements.yaml`. La captura normalizada no guarda HTML crudo, scripts, cookies ni encabezados.

El extractor es heurístico y determinista, no un análisis semántico automático con IA. Conserva saltos de bloque y viñetas, la cita fuente y los encabezados de requisitos/preferencias/responsabilidades, pero se puede equivocar. Todos empiezan en `needs_review`. Las decisiones personales o legales (autorización laboral, ubicación, horario, compensación o viajes) usan `hard_filter: true` por defecto hasta que se revisen explícitamente. Apruebe cada registro; no evalúe borradores pendientes.

Después de revisar las citas y clasificaciones, enumere únicamente los IDs que desea aprobar; los demás quedan rechazados en la misma escritura atómica:

```powershell
uv run truthful-cv vacancy approve-requirements `
  --job JOB-001 `
  --private-root private `
  --approve REQ-001 REQ-002
```

**Resultado esperado:** `approved requirements: JOB-001`. Si falta una aprobación, `vacancy assess` se niega a continuar.

Después de la aprobación, evalúe solo evidencia aprobada y una biblioteca base privada cuyas líneas exactas ya estén revisadas y firmadas:

```powershell
uv run truthful-cv vacancy assess `
  --job JOB-001 `
  --private-root private `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml `
  --base-manifest private/content-library.yaml
```

**Resultado esperado:** `assessed: JOB-001`, `fit-report.yaml` y el subconjunto exacto `tailored-manifest.yaml`, enlazado en el tracker con ruta relativa. La heurística conserva encabezado/resumen estructural y ordena líneas de evidencia por solapamiento requerido/preferido. No redacta ni firma texto. La coincidencia de etiquetas no es una prueba: el nivel automático es solo `absent` o `partial`; `strong` y `deep` requieren decisión semántica humana y justificación no vacía.

Finalice sin la bandera para generar y verificar una sola vez, pero detenerse antes de copiar:

```powershell
uv run truthful-cv vacancy finalize `
  --job JOB-001 `
  --private-root private `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml
```

La salida esperada es `visual_approval_required: JOB-001` y estado `rendered` con SHA-256. Abra `private/generated/JOB-001/cv.pdf` y revise todas las páginas. El sistema no garantiza una página; el verificador aplica el máximo configurado. Solo después repita con `--visual-approved`:

```powershell
uv run truthful-cv vacancy finalize `
  --job JOB-001 `
  --private-root private `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml `
  --visual-approved
```

La segunda invocación no vuelve a construir ni renderizar. Exige el estado `rendered`, comprueba que los bytes aún coincidan con el hash guardado, repite la verificación estricta y copia bytes con hash idéntico. RenderCV se ejecuta sin shell, con rutas absolutas privadas, modo silencioso soportado y stdout/stderr capturados. El sistema no verifica vida continua de la vacante, no inicia sesión, no evita protecciones y no envía solicitudes de empleo; la postulación sigue siendo manual.

Valide el perfil:

```powershell
uv run truthful-cv validate-profile `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml
```

Genere la entrada de RenderCV:

```powershell
uv run truthful-cv build `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml `
  --manifest profile/private/manifests/master.yaml `
  --output generated/master/input.yaml
```

**Resultado esperado:** la validación imprime el ID del perfil con cantidades de afirmaciones y habilidades; `build` imprime la ruta del YAML generado.

## Etapa 10: interpretar la salida

- Código de salida `0`: la operación terminó correctamente.
- Código `1` y `validation error: ...`: los datos de entrada son inválidos, faltan archivos o no se cumplen políticas.
- `manifest policy check failed`: alguna línea no está aprobada, referencia evidencia incorrecta o viola una redline.
- `profile integrity check failed`: hay referencias desconocidas, duplicadas o incompatibles.
- `PDF verification passed`: el PDF superó las comprobaciones automáticas.

Los mensajes de entradas inválidas son deliberadamente concisos y no deben revelar rutas privadas.

**Resultado esperado:** una entrada válida no genera traceback; una inválida termina con un mensaje breve y código `1`.

## Etapa 11: generar y verificar PDFs

Renderice con la versión fijada:

```powershell
uv run rendercv render generated/master/input.yaml `
  --pdf-path rendercv_output/candidate-cv.pdf `
  --dont-generate-markdown `
  --dont-generate-html `
  --dont-generate-png
```

Verifique el PDF:

```powershell
uv run truthful-cv verify-pdf `
  --profile profile/private/master-profile.yaml `
  --sources profile/private/source-register.yaml `
  --manifest profile/private/manifests/master.yaml `
  --pdf generated/master/rendercv_output/candidate-cv.pdf
```

Copie a `deliverables/` únicamente después de la verificación y de una revisión visual manual:

```powershell
Copy-Item generated/master/rendercv_output/candidate-cv.pdf deliverables/candidate-cv.pdf
```

**Resultado esperado:** RenderCV crea el PDF y la CLI imprime `PDF verification passed`. La inspección visual no debe mostrar cortes, solapamientos ni caracteres dañados.

## Etapa 12: ejecutar pruebas y controles

```powershell
uv run pytest
uv run ruff check .
git diff --check
```

Pruebe también los ejemplos:

```powershell
uv run pytest tests/test_samples.py -v
```

**Resultado esperado:** pytest informa cero fallos, Ruff muestra `All checks passed!` y `git diff --check` no reporta errores.

## Etapa 13: resolver errores comunes

| Error | Acción segura |
|---|---|
| `uv` no se reconoce | Cierre y abra PowerShell; confirme que `uv` está en `PATH`. |
| El lock está desactualizado | No quite `--locked` sin revisar; actualice dependencias en una rama separada y ejecute todas las pruebas. |
| `unsupported claim category` | Use únicamente una categoría documentada en `docs/profile-schema.md`. |
| Fecha inválida | Use `YYYY` o `YYYY-MM`; el mes debe estar entre `01` y `12`. |
| Firma exacta no aprobada | Revise la línea y su evidencia; luego regenere firmas conscientemente. |
| Redline encontrada | Elimine o corrija el contenido prohibido; no debilite el verificador. |
| Falta texto en el PDF | Compruebe que RenderCV produjo una capa de texto y que usa el perfil/manifiesto correctos. |
| PDF de más de una página | Acorte contenido verdadero o ajuste diseño; no reduzca hasta hacerlo ilegible. |
| Archivo privado aparece en Git | Deténgase, no confirme cambios y revise `.gitignore` con `git check-ignore -v`. |

**Resultado esperado:** después de corregir la causa, repita la validación completa y obtenga código `0`.

## Etapa 14: actualizar el proyecto de forma segura

Antes de actualizar:

```powershell
git status --short
git switch -c maintenance/update-dependencies
uv lock --upgrade
uv sync --extra dev --extra render --locked
uv run pytest
uv run ruff check .
```

Revise `git diff`, especialmente `uv.lock`, antes de confirmar cambios. No actualice RenderCV o validadores sin regenerar y verificar PDFs de prueba. Mantenga los datos privados fuera del commit.

Para incorporar cambios remotos cuando el árbol esté limpio:

```powershell
git pull --ff-only
```

**Resultado esperado:** las pruebas permanecen verdes y `git status` solo muestra los archivos públicos que decidió modificar.

## Etapa 15: detener, desinstalar o eliminar componentes locales

No hay un servidor permanente. Para detener un comando activo, presione `Ctrl+C`.

Elimine solo el entorno del proyecto:

```powershell
Remove-Item -Recurse -Force .venv
```

Limpie la caché administrada por `uv` si necesita recuperar espacio:

```powershell
uv cache clean
```

Para eliminar toda la copia local, salga de la carpeta y bórrela. Haga antes una copia cifrada de cualquier perfil o PDF privado que deba conservar:

```powershell
Set-Location ..
Remove-Item -Recurse -Force truthful-cv-system
```

No desinstale Git o `uv` si otros proyectos los utilizan. La eliminación local no borra el repositorio privado de GitHub.

**Resultado esperado:** la carpeta o `.venv` deja de existir y no queda ningún proceso del proyecto ejecutándose.

## Lista final de seguridad

- [ ] Los datos reales están en rutas ignoradas.
- [ ] No hay contraseñas, tokens ni claves en YAML, terminales compartidas o commits.
- [ ] Cada afirmación aprobada tiene evidencia registrada.
- [ ] Cada línea exportada fue revisada y firmada exactamente.
- [ ] El perfil, el manifiesto y el PDF pasan sus validaciones.
- [ ] El PDF fue revisado visualmente.
- [ ] Las solicitudes de empleo siguen siendo manuales.
