Scripts del Informe de Avance 1 (tablas 3, 4 y 5 y figuras)

1. exp_tolima_meta.py: corre el experimento (Tolima y Meta, 66 municipios endemicos).
   Uso: python -I exp_tolima_meta.py <ruta_repo_microproyecto-tema3> <carpeta_salida>
   Lee data/processed/features_mensual.parquet del repo y usa aplicar_referencia
   de src/features/build_features.py. Escribe tm_resultados.json y las figuras.

2. build_doc_tm.py: arma el Word del informe a partir de esa salida.
   Uso: python -I build_doc_tm.py <carpeta_salida> <docx_destino>

out/: la salida con la que se hizo el informe entregado (tm_resultados.json y figuras),
para comparar si se vuelve a correr.

Librerias: pandas, numpy, xgboost, lightgbm, pygam, scikit-learn, matplotlib, python-docx.
