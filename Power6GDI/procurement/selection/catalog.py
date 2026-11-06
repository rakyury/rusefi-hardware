"""Reviewed sourcing candidates, 2026-10-25. No network or purchasing actions.

Catalog identity/nominal matching is not electrical qualification of this ECU.
Sources are manufacturer specifications or distributor catalogs; unverified
family-derived order codes are explicitly distinguished by the builder.
"""
CAPS = {}

def cap(size, pf, volts, dielectric, mpn, url, manufacturer='KEMET', tolerance=10):
    CAPS[(size, pf, volts, dielectric)] = dict(manufacturer=manufacturer,
        orderable_mpn=mpn, package=size, ratings=dict(capacitance_pf=pf,
        rated_voltage_v=volts, dielectric=dielectric, tolerance_pct=tolerance,
        temperature_min_c=-55, temperature_max_c=125),
        source_urls=[url], confidence='CATALOG_IDENTITY_AND_NOMINALS',
        qualification='BOARD_QUALIFICATION_PENDING', status='SELECTED_CATALOG_ITEM')

cap('0603',100000,50,'X7R','C0603C104K5RACTU','https://search.kemet.com/download/specsheet/C0603C104K5RACTU')
cap('0805',100000,100,'X7R','C0805C104K1RACTU','https://www.mouser.com/datasheet/3/72/1/C0805C104K1RACTU.pdf')
cap('0603',10000,50,'X7R','C0603C103K5RACTU','https://www.digikey.com/en/products/detail/kemet/C0603C103K5RACTU/411090')
cap('0603',1000,100,'C0G','C0603C102J1GACTU','https://search.kemet.com/download/specsheet/C0603C102J1GACTU',tolerance=5)
cap('0603',120,50,'C0G','C0603C121F5GACTU','https://www.digikey.com/en/products/detail/kemet/C0603C121F5GACTU/2199842',tolerance=1)
cap('0603',1000000,25,'X7R','C0603C105K3RACTU','https://search.kemet.com/download/specsheet/C0603C105K3RACTU')
cap('0805',1000000,50,'X7R','C0805C105K5RACTU','https://search.kemet.com/component-documentation/download/specsheet/C0805C105K5RACTU')
cap('0603',2200000,10,'X7R','C0603C225K8RACTU','https://www.tme.com/us/en-us/details/c0603c225k8rac/mlcc-smd-capacitors/kemet/c0603c225k8ractu/')
cap('0805',2200000,16,'X7R','C0805C225K4RACTU','https://search.kemet.com/download/specsheet/C0805C225K4RACTU')
cap('0805',22000,100,'X7R','C0805C223K1RACTU','https://www.tme.com/Document/1eb495a6db632c9d0f71cb50aeea4240/C0805C223K1RACTU.pdf')
cap('0805',220000,100,'X7R','C0805C224K1RACTU','https://content.kemet.com/datasheets/CER_ENG_KIT_30.pdf')
cap('0805',470000,50,'X7R','C0805C474K5RACTU','https://content.kemet.com/datasheets/CER_ENG_KIT_30.pdf')
cap('1206',10000000,16,'X7R','C1206C106K4RACTU','https://search.kemet.com/component-documentation/download/specsheet/C1206C106K4RACTU')
cap('1210',10000000,100,'X7R','C3225X7R2A106K250AC','https://www.digikey.com/en/products/detail/tdk/C3225X7R2A106K250AC/15930207','TDK')
cap('0603',4700000,16,'X7R','GMC10X7R475K16NT','https://www.digikey.com/en/products/detail/cal-chip-electronics-inc/GMC10X7R475K16NT/22471820','Cal-Chip Electronics')
cap('0805',10000000,25,'X7R','GMC21X7R106K25NT','https://www.digikey.com/en/products/detail/cal-chip-electronics-inc/GMC21X7R106K25NT/22640097','Cal-Chip Electronics')

# Exact catalog identities checked in authorized distributor catalogs.
_VERIFIED_CAPS = [
('0603',1000,50,'X7R','C0603C102K5RACTU','411357'),
('0805',330000,50,'X7R','C0805C334K5RACTU','2212621'),
('0603',4700,100,'C0G','C0603C472J1GACTU','3737137'),
('0603',330,100,'C0G','C0603C331J1GACTU',None),
('0603',470,100,'C0G','C0603C471J1GACTU','3471644'),
('0603',47,100,'C0G','C0603C470J1GACTU','2200767'),
('0603',3300,50,'C0G','C0603C332J5GACTU','2200552'),
('0805',3300,50,'C0G','C0805C332J5GACTU','3739599'),
('0805',180,50,'C0G','C0805C181J5GACTU','411125'),
('0805',1000,100,'C0G','C0805C102J1GACTU','411136'),
('0805',47000,100,'X7R','C0805C473K1RACTU','2212858'),
('0603',33000,50,'X7R','C0603C333K5RACTU','2200581'),
('1206',1000000,50,'X7R','C1206C105K5RACTU','2215096'),
('1210',22000000,16,'X7R','C1210C226K4RACTU','5023254'),
]
for size,pf,v,d,mpn,digid in _VERIFIED_CAPS:
    url=('https://www.digikey.com/en/products/detail/kemet/'+mpn+'/'+digid if digid else
         'https://search.kemet.com/download/specsheet/'+mpn)
    cap(size,pf,v,d,mpn,url,tolerance=5 if d=='C0G' else 10)
cap('0603',330000,25,'X7R','0603B334K250NT','https://www.lcsc.com/product-detail/C1615.html','FH')

# Active precision family chosen instead of the ERA-A candidates with EOL notices.
# RNCF current manufacturer datasheet is the rating authority; distributor catalog
# confirms the individual resistance/order code. Procurement availability is separate.
PRECISION = {}
for size,ohms,code,ident in [
 ('0603',10000,'10K0','4250700'),('0603',100000,'100K','16890122'),
 ('0603',102000,'102K','6262325'),('0603',147000,'147K','1710285'),
 ('0603',30000,'30K0','16890249'),('0603',4990,'4K99','16890134'),
 ('0805',140000,'140K','6240027'),('0805',470000,'470K','16890068'),
 ('0603',220,'220R',None)]:
    mpn='RNCF'+size+'BTE'+code
    url=('https://www.digikey.com/en/products/detail/stackpole-electronics-inc/'+mpn+'/'+ident if ident else
         'https://www.mouser.ca/en/ProductDetail/SEI-Stackpole/RNCF0603BTE220R')
    PRECISION[(size,ohms)]=dict(manufacturer='Stackpole Electronics',orderable_mpn=mpn,package=size,
      ratings=dict(resistance_ohm=ohms,tolerance_pct=0.1,tcr_ppm_c=25,power_w=0.167 if size=='0603' else 0.25,
        working_voltage_v=75 if size=='0603' else 150,power_reference_temperature_c=70,
        temperature_min_c=-55,temperature_max_c=155,technology='thin film',aec_q200=True),
      source_urls=[url,'https://www.seielect.com/Catalog/SEI-RNCF.pdf'],
      confidence='CATALOG_IDENTITY_AND_NOMINALS',status='SELECTED_CATALOG_ITEM',qualification='BOARD_QUALIFICATION_PENDING')
    if ohms in (102000,147000,140000):
        PRECISION[(size,ohms)]['gaps']=['Exact part is cataloged but small-quantity supply not confirmed; distributor lists non-stock/reel-only ordering.']
PRECISION[('0603',9760)]=dict(manufacturer='Vishay',orderable_mpn='TNPW06039K76BEEA',package='0603',
    ratings=dict(resistance_ohm=9760,tolerance_pct=0.1,tcr_ppm_c=25,power_w=0.21,working_voltage_v=75,
      temperature_min_c=-55,temperature_max_c=175,technology='thin film',aec_q200=True),
    source_urls=['https://www.digikey.com/en/products/detail/vishay-dale/TNPW06039K76BEEA/1606880',
      'https://www.vishay.com/docs/28758/tnpw_e3.pdf'],confidence='CATALOG_IDENTITY_AND_NOMINALS',
    status='SELECTED_CATALOG_ITEM',qualification='BOARD_QUALIFICATION_PENDING')

SPECIAL = {
 'R5201':dict(manufacturer='Vishay',orderable_mpn='PNM0603E2502BST5',package='0603',ratings=dict(resistance_ohm=25000,tolerance_pct=0.1,tcr_ppm_c=25,power_w=0.1),source_urls=['https://www.ti.com.cn/cn/lit/df/tidrav4/tidrav4.pdf'],confidence='MANUFACTURER_REFERENCE_BOM',status='SELECTED_CATALOG_ITEM'),
 'R5301':dict(manufacturer='Stackpole Electronics',orderable_mpn='RNCF0603BTE32K0',package='0603',ratings=dict(resistance_ohm=32000,tolerance_pct=0.1,tcr_ppm_c=25,power_w=0.167,temperature_min_c=-55,temperature_max_c=155),source_urls=['https://www.digikey.com/en/products/detail/stackpole-electronics-inc/RNCF0603BTE32K0/1710094'],confidence='CATALOG_IDENTITY_AND_NOMINALS',status='SELECTED_CATALOG_ITEM'),
}

SHUNT = dict(manufacturer='Vishay',orderable_mpn='WSLP1206R0100FEA',package='1206',
    ratings=dict(resistance_ohm=0.01,tolerance_pct=1,tcr_ppm_c=75,power_w=1,
        power_reference_temperature_c=70,temperature_min_c=-65,temperature_max_c=170,
        technology='metal strip',terminals=2,pcb_sense_pads=4,
        pulse_rating='Use manufacturer pulse-duration curve; repetitive B58 current/energy not qualified'),
    source_urls=['https://www.vishay.com/docs/30122/wslp.pdf',
        'https://www.digikey.com/en/product-highlight/v/vishay-dale/wslp1206-very-high-power-1-w-surface-mount-power-metal-strip-resistor'],
    confidence='CATALOG_IDENTITY_AND_NOMINALS',status='SELECTED_CONDITIONAL',
    qualification='PULSE_THERMAL_AND_KELVIN_LAYOUT_REVIEW_REQUIRED')

# Small-quantity alternatives to cataloged but non-stock RNCF values.
for ohms,code,ident in [(102000,'102K','1606996'),(147000,'147K','1607012')]:
    item=dict(PRECISION[('0603',9760)])
    item['ratings']=dict(item['ratings'],resistance_ohm=ohms)
    item['orderable_mpn']='TNPW0603'+code+'BEEA'
    item['source_urls']=['https://www.digikey.com/en/products/detail/vishay-dale/'+item['orderable_mpn']+'/'+ident,'https://www.vishay.com/docs/28758/tnpw_e3.pdf']
    PRECISION[('0603',ohms)]=item
PRECISION[('0805',140000)]=dict(manufacturer='Susumu',orderable_mpn='RG2012P-1403-B-T5',package='0805',
    ratings=dict(resistance_ohm=140000,tolerance_pct=0.1,tcr_ppm_c=25,power_w=0.125,working_voltage_v=150,
      temperature_min_c=-55,temperature_max_c=155,technology='thin film',aec_q200=True),
    source_urls=['https://www.digikey.com/en/products/detail/susumu/RG2012P-1403-B-T5/1241065'],
    confidence='CATALOG_IDENTITY_AND_NOMINALS',status='SELECTED_CATALOG_ITEM',qualification='BOARD_QUALIFICATION_PENDING')
