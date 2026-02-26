import io, re
try:
    import segno
except ImportError:
    segno = None

def generate_epc_qr(name: str, iban: str, amount: float, reference: str, bic: str = ""):
    if not segno: return None, None
    name = str(name)[:70].strip()
    iban = re.sub(r'\s+', '', str(iban)).upper()
    amount_str = f"EUR{float(amount):.2f}" if amount else ""
    ref = str(reference)[:140].strip()
    bic = str(bic)[:11].upper().strip()

    payload = f"BCD\n002\n1\nSCT\n{bic}\n{name}\n{iban}\n{amount_str}\n\n{ref}\n"
    
    qr = segno.make(payload, error='M')
    out = io.BytesIO()
    qr.save(out, kind='png', scale=6, border=2)
    return out.getvalue(), payload
