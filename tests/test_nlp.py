from app.nlp import classify, normalize
def test_original_pipeline_detects_multiple_aspects():
    x=classify("La sala genial pero esperamos 25 minutos y hacía muchísimo calor")
    aspects={a["aspect"] for a in x["aspects"]}; assert {"espera","temperatura"}<=aspects
def test_empty_review_is_neutral(): assert classify("")["sentiment"]=="neutral"
def test_normalization(): assert normalize("  HOLA   Mundo ")=="hola mundo"
