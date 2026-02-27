import xml.etree.ElementTree as ET
import uuid, os
from datetime import datetime, timezone

def generate_pain001_xml(creditor_name: str, creditor_iban: str, amount: float, reference: str, creditor_bic: str = ""):
    msg_id = "EA-" + uuid.uuid4().hex[:12].upper()
    cre_dt_tm = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    
    ET.register_namespace("", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
    doc = ET.Element("{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}Document")
    cstmr = ET.SubElement(doc, "CstmrCdtTrfInitn")

    grp = ET.SubElement(cstmr, "GrpHdr")
    ET.SubElement(grp, "MsgId").text = msg_id
    ET.SubElement(grp, "CreDtTm").text = cre_dt_tm
    ET.SubElement(grp, "NbOfTxs").text = "1"
    ET.SubElement(grp, "CtrlSum").text = f"{amount:.2f}"
    ET.SubElement(ET.SubElement(grp, "InitgPty"), "Nm").text = "EA User"

    pmt = ET.SubElement(cstmr, "PmtInf")
    ET.SubElement(pmt, "PmtInfId").text = msg_id + "-1"
    ET.SubElement(pmt, "PmtMtd").text = "TRF"
    ET.SubElement(pmt, "NbOfTxs").text = "1"
    ET.SubElement(pmt, "CtrlSum").text = f"{amount:.2f}"
    
    svc_lvl = ET.SubElement(ET.SubElement(pmt, "PmtTpInf"), "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    ET.SubElement(pmt, "ReqdExctnDt").text = datetime.now().strftime("%Y-%m-%d")

    ET.SubElement(ET.SubElement(pmt, "Dbtr"), "Nm").text = "EA User"
    ET.SubElement(ET.SubElement(ET.SubElement(pmt, "DbtrAcct"), "Id"), "IBAN").text = "AT000000000000000000"
    ET.SubElement(pmt, "ChrgBr").text = "SLEV"

    cdt = ET.SubElement(pmt, "CdtTrfTxInf")
    ET.SubElement(ET.SubElement(cdt, "PmtId"), "EndToEndId").text = msg_id
    ET.SubElement(ET.SubElement(cdt, "Amt"), "InstdAmt", Ccy="EUR").text = f"{amount:.2f}"

    fin = ET.SubElement(ET.SubElement(cdt, "CdtrAgt"), "FinInstnId")
    if creditor_bic: ET.SubElement(fin, "BIC").text = creditor_bic
    else: ET.SubElement(fin, "Othr").text = "NOTPROVIDED"

    ET.SubElement(ET.SubElement(cdt, "Cdtr"), "Nm").text = creditor_name[:70]
    ET.SubElement(ET.SubElement(ET.SubElement(cdt, "CdtrAcct"), "Id"), "IBAN").text = creditor_iban.replace(" ", "")

    ET.SubElement(ET.SubElement(cdt, "RmtInf"), "Ustrd").text = (reference or "Rechnung")[:140]

    return ET.tostring(doc, encoding="utf-8", xml_declaration=True)
