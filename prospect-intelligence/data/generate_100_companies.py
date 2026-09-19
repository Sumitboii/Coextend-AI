"""
Curated list of 100 real-world façade, cladding, roofing, and building envelope
contractors in the UK, US, and Canada, matching Coextend's Ideal Customer Profile.
"""
import json
import os

COMPANIES_100 = [
    # --- UK Specialists (45 companies) ---
    {"company_name": "Lindner Prater Ltd", "website": "https://www.lindner-group.com", "region": "UK"},
    {"company_name": "Harley Curtain Wall Ltd", "website": "https://www.harleyfacades.co.uk", "region": "UK"},
    {"company_name": "Alucraft Ltd", "website": "https://www.alucraft.co.uk", "region": "UK"},
    {"company_name": "Colorminium London Ltd", "website": "https://www.colorminium.com", "region": "UK"},
    {"company_name": "FK Group Ltd", "website": "https://www.fkgroup.co.uk", "region": "UK"},
    {"company_name": "Apex Facades Ltd", "website": "https://www.apexfacades.co.uk", "region": "UK"},
    {"company_name": "Scheldebouw UK Ltd", "website": "https://www.permasteelisagroup.com", "region": "UK"},
    {"company_name": "Focchi UK Ltd", "website": "https://www.focchi.it", "region": "UK"},
    {"company_name": "Octatube UK", "website": "https://www.octatube.nl", "region": "UK"},
    {"company_name": "Yuanda UK Ltd", "website": "https://www.yuanda.co.uk", "region": "UK"},
    {"company_name": "Severfield Facades", "website": "https://www.severfield.com", "region": "UK"},
    {"company_name": "Structura UK Ltd", "website": "https://www.structura-uk.com", "region": "UK"},
    {"company_name": "Topek Ltd", "website": "https://www.topek.co.uk", "region": "UK"},
    {"company_name": "Telling Architectural Ltd", "website": "https://www.telling.co.uk", "region": "UK"},
    {"company_name": "Spanwall Facades Ltd", "website": "https://www.spanwall.com", "region": "UK"},
    {"company_name": "CGL Facades Ltd", "website": "https://www.cglfacades.com", "region": "UK"},
    {"company_name": "Speedclad Ltd", "website": "https://www.speedclad.co.uk", "region": "UK"},
    {"company_name": "Bailey Total Building Envelope", "website": "https://www.bailey-uk.com", "region": "UK"},
    {"company_name": "Stanmore Contractors Ltd", "website": "https://www.stanmore.co.uk", "region": "UK"},
    {"company_name": "Red Systems Ltd", "website": "https://www.redsystems.co.uk", "region": "UK"},
    {"company_name": "Charles Henshaw & Sons Ltd", "website": "https://www.henshaw.co.uk", "region": "UK"},
    {"company_name": "Britplas Facades Ltd", "website": "https://www.britplas.com", "region": "UK"},
    {"company_name": "Task Building Envelope Ltd", "website": "https://www.taskfacades.co.uk", "region": "UK"},
    {"company_name": "Fleetwood Architectural Aluminium", "website": "https://www.faa.co.uk", "region": "UK"},
    {"company_name": "CoverStructure Ltd", "website": "https://www.coverstructure.com", "region": "UK"},
    {"company_name": "Maple Sunscreening Ltd", "website": "https://www.maplesunscreening.co.uk", "region": "UK"},
    {"company_name": "Metalline Architectural Ltd", "website": "https://www.metalline.co.uk", "region": "UK"},
    {"company_name": "Glass Solutions Ltd", "website": "https://www.glasssolutions.co.uk", "region": "UK"},
    {"company_name": "Glazzard Architectural", "website": "https://www.glazzard.co.uk", "region": "UK"},
    {"company_name": "GIG Fassaden UK", "website": "https://www.gig.at", "region": "UK"},
    {"company_name": "Wintech Facade Engineering", "website": "https://www.wintech-group.com", "region": "UK"},
    {"company_name": "Astec Projects Ltd", "website": "https://www.astecprojects.com", "region": "UK"},
    {"company_name": "Schneider Facades UK", "website": "https://www.schneider-facades.com", "region": "UK"},
    {"company_name": "Dane Architectural Systems", "website": "https://www.danearchitectural.co.uk", "region": "UK"},
    {"company_name": "English Architectural Glazing (EAG)", "website": "https://www.eag.co.uk", "region": "UK"},
    {"company_name": "Glamalco Ltd", "website": "https://www.glamalco.co.uk", "region": "UK"},
    {"company_name": "Horbury Group Ltd", "website": "https://www.horburygroup.com", "region": "UK"},
    {"company_name": "Aliva UK Ltd", "website": "https://www.alivauk.com", "region": "UK"},
    {"company_name": "RCM Building Boards", "website": "https://www.buildingboards.co.uk", "region": "UK"},
    {"company_name": "CA Group Roofing & Cladding", "website": "https://www.cagroup.co.uk", "region": "UK"},
    {"company_name": "Lakesmere Building Envelope", "website": "https://www.lakesmere.com", "region": "UK"},
    {"company_name": "Proactive Cladding Ltd", "website": "https://www.proactivecladding.co.uk", "region": "UK"},
    {"company_name": "Elite Cladding Systems Ltd", "website": "https://www.elitecladding.co.uk", "region": "UK"},
    {"company_name": "Taylor Maxwell Facades", "website": "https://www.taylormaxwell.co.uk", "region": "UK"},
    {"company_name": "Downing Cladding Ltd", "website": "https://www.downing.com", "region": "UK"},

    # --- US Specialists (40 companies) ---
    {"company_name": "Enclos Corp", "website": "https://www.enclos.com", "region": "US"},
    {"company_name": "Harmon Inc", "website": "https://www.harmoninc.com", "region": "US"},
    {"company_name": "Crown Corr Inc", "website": "https://www.crowncorr.com", "region": "US"},
    {"company_name": "Walters & Wolf", "website": "https://www.waltersandwolf.com", "region": "US"},
    {"company_name": "Benson Industries LLC", "website": "https://www.bensonglobal.com", "region": "US"},
    {"company_name": "W&W Glass LLC", "website": "https://www.wwglass.com", "region": "US"},
    {"company_name": "Permasteelisa North America", "website": "https://www.permasteelisagroup.com", "region": "US"},
    {"company_name": "Island Exterior Fabricators", "website": "https://www.islandef.com", "region": "US"},
    {"company_name": "New Hudson Facades", "website": "https://www.newhudsonfacades.com", "region": "US"},
    {"company_name": "ASI Limited", "website": "https://www.asilimited.com", "region": "US"},
    {"company_name": "Bagatelos Architectural Glass", "website": "https://www.bagatelos.com", "region": "US"},
    {"company_name": "Architectural Wall Systems (AWS)", "website": "https://www.archwall.com", "region": "US"},
    {"company_name": "Pioneer Cladding & Glazing", "website": "https://www.pioneerglazing.com", "region": "US"},
    {"company_name": "TSI Exterior Wall Systems", "website": "https://www.tsicorp.com", "region": "US"},
    {"company_name": "Gamma USA Inc", "website": "https://www.gammagroup.com", "region": "US"},
    {"company_name": "Architectural Glass & Aluminum (AGA)", "website": "https://www.aga-ca.com", "region": "US"},
    {"company_name": "Karas & Karas Glass Co", "website": "https://www.karasglass.com", "region": "US"},
    {"company_name": "Advanced Glazing Contractors", "website": "https://www.advancedglazing.com", "region": "US"},
    {"company_name": "Bunting Graphics & Facades", "website": "https://www.buntingarchitecturalmetals.com", "region": "US"},
    {"company_name": "Haley-Greer Inc", "website": "https://www.haleygreer.com", "region": "US"},
    {"company_name": "National Enclosure Company", "website": "https://www.nationalenclosure.com", "region": "US"},
    {"company_name": "Alliance Exterior Construction", "website": "https://www.allianceexterior.com", "region": "US"},
    {"company_name": "Erie Architectural Products", "website": "https://www.erieap.com", "region": "US"},
    {"company_name": "Super Sky Products Enterprises", "website": "https://www.supereky.com", "region": "US"},
    {"company_name": "Sentech Architectural Systems", "website": "https://www.sentechas.com", "region": "US"},
    {"company_name": "Glass Solutions Inc (US)", "website": "https://www.glasssolutionsinc.com", "region": "US"},
    {"company_name": "Novum Structures LLC", "website": "https://www.novumstructures.com", "region": "US"},
    {"company_name": "Sobotec Ltd (US)", "website": "https://www.sobotec.com", "region": "US"},
    {"company_name": "Dynamic Glass LLC", "website": "https://www.dynamicglass.com", "region": "US"},
    {"company_name": "Giroux Glass Inc", "website": "https://www.girouxglass.com", "region": "US"},
    {"company_name": "W&W Steel & Glass", "website": "https://www.wwsteel.com", "region": "US"},
    {"company_name": "Alexander Metals Inc", "website": "https://www.alexandermetalsinc.com", "region": "US"},
    {"company_name": "Midwest Curtainwalls Inc", "website": "https://www.midwestcurtainwalls.com", "region": "US"},
    {"company_name": "Apex Glazing US", "website": "https://www.apexglazing.com", "region": "US"},
    {"company_name": "Custom Metalcraft Facades", "website": "https://www.custom-metalcraft.com", "region": "US"},
    {"company_name": "Covenant Glass Inc", "website": "https://www.covenantglass.com", "region": "US"},
    {"company_name": "Kenney Glass Company", "website": "https://www.kenneyglass.com", "region": "US"},
    {"company_name": "Façade Technology LLC", "website": "https://www.facadetechnology.com", "region": "US"},
    {"company_name": "Atlantic Architectural Glass", "website": "https://www.atlanticglass.com", "region": "US"},
    {"company_name": "T&T Facades USA", "website": "https://www.ttfacades.com", "region": "US"},

    # --- Canada Specialists (15 companies) ---
    {"company_name": "Flynn Group of Companies", "website": "https://www.flynncompanies.com", "region": "Canada"},
    {"company_name": "Ferguson Neudorf Glass Inc", "website": "https://www.fnglass.com", "region": "Canada"},
    {"company_name": "BVGlazing Systems", "website": "https://www.bvglazing.com", "region": "Canada"},
    {"company_name": "Toro Aluminum Ltd", "website": "https://www.toroaluminum.com", "region": "Canada"},
    {"company_name": "Sotawall Inc", "website": "https://www.sotawall.com", "region": "Canada"},
    {"company_name": "Northern Facades Ltd", "website": "https://www.northernfacades.com", "region": "Canada"},
    {"company_name": "State Window Corporation", "website": "https://www.statewindowcorp.com", "region": "Canada"},
    {"company_name": "Antamex Building Envelope", "website": "https://www.antamex.com", "region": "Canada"},
    {"company_name": "Skyreach Architectural", "website": "https://www.skyreach.ca", "region": "Canada"},
    {"company_name": "Inland Glass & Aluminum Ltd", "website": "https://www.inlandglass.ca", "region": "Canada"},
    {"company_name": "Apex Aluminum Systems", "website": "https://www.apexaluminum.ca", "region": "Canada"},
    {"company_name": "Stella Glass Structures", "website": "https://www.stellaglasshardware.com", "region": "Canada"},
    {"company_name": "Aluminum Curtainwall Systems", "website": "https://www.aluminumcurtainwall.com", "region": "Canada"},
    {"company_name": "Tremco CPG Canada", "website": "https://www.tremcocpg.com", "region": "Canada"},
    {"company_name": "Ametis Building Envelope", "website": "https://www.ametis.ca", "region": "Canada"},
]

def main():
    os.makedirs("prospect-intelligence/data", exist_ok=True)
    out_path = "prospect-intelligence/data/companies_100.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(COMPANIES_100, f, indent=2)
    print(f"Generated {len(COMPANIES_100)} companies dataset at {out_path}")

if __name__ == "__main__":
    main()
