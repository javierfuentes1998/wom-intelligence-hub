import csv, io
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

class Connector(ABC):
    @abstractmethod
    def preview(self, source, limit=20): ...
    @abstractmethod
    def rows(self, source): ...

class CSVConnector(Connector):
    encodings=("utf-8-sig","utf-8","cp1252","latin-1")
    def decode(self,data:bytes):
        for enc in self.encodings:
            try:return data.decode(enc),enc
            except UnicodeDecodeError:pass
        raise ValueError("Encoding no soportado")
    def rows(self,source):
        data=source if isinstance(source,bytes) else Path(source).read_bytes();text,enc=self.decode(data)
        sample=text[:4096];dialect=csv.Sniffer().sniff(sample,delimiters=",;")
        return list(csv.DictReader(io.StringIO(text),dialect=dialect)),{"encoding":enc,"delimiter":dialect.delimiter}
    def preview(self,source,limit=20):
        rows,meta=self.rows(source);return {"columns":list(rows[0]) if rows else [],"rows":rows[:limit],"total":len(rows),**meta}

class ExcelConnector(Connector):
    def rows(self,source):
        import pandas as pd
        df=pd.read_excel(source,dtype=str);return df.fillna("").to_dict("records"),{"sheet":"first"}
    def preview(self,source,limit=20):
        rows,meta=self.rows(source);return {"columns":list(rows[0]) if rows else [],"rows":rows[:limit],"total":len(rows),**meta}

class DatabaseConnector(Connector):
    def preview(self,source,limit=20): raise NotImplementedError("Pendiente de credenciales y esquema reales")
    def rows(self,source): raise NotImplementedError("Pendiente de credenciales y esquema reales")
class APIConnector(DatabaseConnector): pass
class BookingConnector(DatabaseConnector): pass

def parse_decimal(value):
    s=str(value).strip().replace("€","").replace(" ","")
    if "," in s and "." in s:s=s.replace(".","").replace(",",".")
    elif "," in s:s=s.replace(",",".")
    return float(s)
def parse_date(value):
    for f in ("%d/%m/%Y","%Y-%m-%d","%d-%m-%Y"):
        try:return datetime.strptime(str(value).strip(),f).date()
        except ValueError:pass
    raise ValueError(f"Fecha inválida: {value}")
def validate_rows(rows,mapping,required):
    valid=[];errors=[]
    for i,row in enumerate(rows,2):
        mapped={target:row.get(source,"") for target,source in mapping.items()}
        missing=[x for x in required if not str(mapped.get(x,"")).strip()]
        if missing:errors.append({"row":i,"error":f"Campos vacíos: {', '.join(missing)}","data":row})
        else:valid.append(mapped)
    return valid,errors
