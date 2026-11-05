"""Review calculations, explicit load allocations (not measured maxima)."""
import json, math
from pathlib import Path
HERE=Path(__file__).resolve().parent

def calculate():
    rail33={'STM32F767 + ADC + clocks':0.350,'20 analog amplifiers and filters':0.050,'6 ignition comparators, timers and gates':0.075,'safety, SENT, digital buffers and SPI':0.100,'2 H-bridge GPIO/pullups':0.010,'CAN VIO, LIN RX and misc pullups':0.030,'other core IO and LEDs':0.050}
    rail5={'1 WBO node (incl local LDO)':0.200,'2 TCAN1042 incl specified bus fault (0.120A each)':0.240,'6 ignition gate drivers incl dynamic reserve':0.075,'6 TLE9104 logic supplies (0.030A each)':0.180,'MAX9924 + TPIC8101 + level translators':0.080,'Hall/pullups/sensor references and other logic':0.050}
    conversion=3.3*1.0/(4.90*0.85)
    total5=sum(rail5.values())+conversion
    v5lo=.987*(1+100000*.999/(25000*1.001))-60e-9*100000*1.001
    v5hi=1.017*(1+100000*1.001/(25000*.999))+60e-9*100000*1.001
    v33lo=.8*.977*(1+100000*.999/(32000*1.001))-100e-9*100000*1.001
    v33hi=.8*1.028*(1+100000*1.001/(32000*.999))+100e-9*100000*1.001
    ripple5=5.03*(1-5.03/60)/(6.8e-6*.8*440e3)
    ripple33=3.3*(1-3.3/5.12)/(2.2e-6*.8*1e6)
    battery=5.03*2/(6.4*.85)+.600+.150
    result={'status':'ALLOCATED_ENVELOPES_NOT_MEASURED_OR_THERMALLY_QUALIFIED','rail3v3_allocations_A':rail33,'rail3v3_allocated_A':round(sum(rail33.values()),6),'rail3v3_target_A':1.0,'rail5v_direct_allocations_A':rail5,'rail5v_direct_A':round(sum(rail5.values()),6),'rail5v_3v3_conversion_A':round(conversion,6),'rail5v_combined_A':round(total5,6),'rail5v_target_A':2.0,'rail5v_headroom_A':round(2-total5,6),'conversion_assumption':{'3v3_load_A':1,'input_min_V':4.9,'efficiency_floor_assumed_not_guaranteed':.85},'feedback_static_bounds_V':{'5V':[round(v5lo,5),round(v5hi,5)],'3V3_PSM':[round(v33lo,5),round(v33hi,5)]},'ripple_5v_A_60V_Lminus20_f440k':ripple5,'peak_5v_A_at2A':2+ripple5/2,'ripple_3v3_A_5p12V_Lminus20_f1MHz_assumed':ripple33,'peak_3v3_A_at1A':1+ripple33/2,'protected_battery_A_at6p4V_2A5V_plus_sensors_LIN':battery,'diode_estimated_W_from_ST_formula':.51*battery+.02*battery*battery,'EN_rise_protected_nom_V':1.204*5.7,'EN_rise_static_bounds_V':[1.14*(1+470*.999/(100*1.001))-.2e-6*470000*1.001,1.25*(1+470*1.001/(100*.999))+.2e-6*470000*1.001],'Cff_estimate_F_at156uF':1/(2*math.pi*(15.46/(5.03*156e-6)))*math.sqrt(1/(100000*20000)),'excluded_from_logic_rails':['6 GDI /2HPFP power and local VCC5; main3V3 VCCIO is NOT excluded','6 PI coil current and 16 aux load current','6 ignition primary current','2 H-bridge motor current','1 WBO heater current','SENSOR_5V_A/B tracker output load (battery-fed)'],'open_validation':['efficiency and thermal at minimum input/hot enclosure','capacitor manufacturer DC bias curves and exact order codes','LM76003 loop response with total5V bus capacitance','TPS62130A dynamic switching frequency, short circuit and hot inductor margin','supply backfeed through IO and programmer','input TVS/fuse pulse coordination','actual WBO node and actuator-control logic current across faults']}
    result['unresolved_3v3_loads'] = [
        {'load':'SD card at J1502.4 via R1520', 'allocated_A':None,
         'closure':'Selected card peak current and duration required'},
        {'load':'PT2001 VCCIO at U201.17/U301.17 via R221/R321', 'allocated_A':None,
         'closure':'Full manufacturer electrical maxima required'},
    ]
    result['rail3v3_remaining_unvalidated_envelope_A'] = round(
        result['rail3v3_target_A']-result['rail3v3_allocated_A'],6)
    result['allocation_complete'] = False
    return result

if __name__=='__main__':
    data=calculate()
    (HERE/'power_budget.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))
