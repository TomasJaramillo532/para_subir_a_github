#### Ficha del modelo · CaféScore v1 (noviembre de 2026)

**Dueño.** Equipo consultor del proyecto CaféScore (Grupo 4, Minería de Datos ADMI 2559, Universidad de los Andes), por encargo de la fundadora de Cereza Café. *Completar con nombres y contacto del responsable de mantenimiento.*

**Objetivo.** Priorizar en qué zonas de Bogotá vale la pena invertir un estudio de campo (COP 20 M por zona) para buscar local para las dos tiendas de 2027.

**Para qué sirve.**
- Ordenar las 3.275 zonas urbanas por su parecido con las zonas que hoy sostienen cafés.
- Señalar zonas con menos cafés de los que su perfil sugiere (oportunidad) y zonas con más (saturadas).
- Informar la distancia a las tiendas actuales y un arriendo de referencia para filtrar.

**Para qué NO sirve.**
- No predice ventas, rentabilidad ni la supervivencia de una tienda.
- No autoriza inversiones ni reemplaza el estudio de campo, la visita a locales o el análisis de crédito.
- No mide el arriendo real ni el uso del suelo permitido.
- No debe usarse para evaluar personas, hogares o negocios individuales.

**Modelos.**
- Clasificador: regresión logística (C = 0,01) con transformación logarítmica y estandarización; 27 variables (23 originales + 4 construidas). Umbral 0,25, elegido minimizando el costo de errores (FN = COP 60 M, FP = COP 20 M) en validación cruzada por bloques.
- Conteo: regresión de Poisson (alpha = 1,0) para los cafés esperados, con la misma partición.
- Puntajes del mapa: predicciones fuera de bloque (validación cruzada por grupos de 5 pliegues sobre los 108 bloques).

**Datos de entrenamiento.** 2.543 celdas de 86 bloques (semilla 2559); prueba en 732 celdas de 22 bloques. Fuentes: Overture Maps (septiembre de 2026), Foursquare OS Places (2011–2016), OpenStreetMap (2026), Catastro de Bogotá (2026), TransMilenio (septiembre de 2025).

**Desempeño en prueba.** Costo de errores COP 5.880 M frente a COP 6.140 M de la regla simple; diferencia −260 M con IC 95 % [−800; +220]: no se demuestra que el modelo supere a la regla. AUC 0,79; sensibilidad 0,69; precisión 0,37.

**Sesgos y riesgos conocidos.**
- *Sesgo de registro:* Overture y Foursquare cubren mejor zonas comerciales y de mayor ingreso; un 0 puede ser un café no registrado.
- *Sesgo hacia lo existente:* el modelo aprende dónde hay cafés hoy, lo que puede reforzar la concentración en el corredor oriental y subestimar zonas emergentes.
- *Datos desactualizados:* Foursquare es histórico y las obras del metro cambiarán la movilidad.
- *Colinealidad:* las variables de actividad comercial están muy correlacionadas; los pesos individuales no deben leerse como efectos.
- *Supuestos de despliegue (v1):* la definición de clases, el arriendo de referencia y el radio de canibalización son propuestas pendientes de validación.

**Privacidad (Ley 1581 de 2012).** El modelo usa solo datos agregados por celda de ~0,1 km² provenientes de fuentes abiertas. No contiene datos personales. La aplicación publicada no incluye nombres de negocios ni el archivo original del curso. Si en el futuro se incorporan datos de clientes de Cereza (ventas, tarjetas de fidelización), deben anonimizarse, contar con autorización de tratamiento y agregarse por zona antes de entrar al modelo.

**Monitoreo y revisión.**
- Revisar cada seis meses o cuando se publique una nueva versión de Overture Maps.
- Revisar antes de cada decisión de apertura con los resultados de los estudios de campo (¿las zonas estudiadas resultaron aptas?).
- Recalcular cuando entre en operación la primera línea del metro o cambien las troncales.
- Indicadores: precisión de los estudios de campo, aperturas reales en zonas Oportunidad frente a comparables y estabilidad del ranking.

**Cuándo dejar de usarlo.**
- Si en dos revisiones seguidas el modelo cuesta más que la regla simple en datos nuevos.
- Si las fuentes dejan de actualizarse por más de 18 meses.
- Si los estudios de campo muestran de forma sistemática que las zonas Oportunidad no tienen locales comerciales viables.

**Condiciones de uso.** Herramienta de apoyo a la decisión. Cualquier inversión requiere estudio de campo, verificación del uso del suelo y evaluación financiera independientes. Atribución obligatoria: © colaboradores de OpenStreetMap.
