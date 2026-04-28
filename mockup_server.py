from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import time

app = FastAPI(title="Antigravity Mockup Server (Catena-X & CBAM)")

# Enable CORS for the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock Data Storage
latest_pcf_data = {}

class EmissionsData(BaseModel):
    equipment_id: str
    fuel_usage_kg: float
    electricity_kwh: float
    precursors_emissions_kg: float
    production_kg: float
    coproduct_ratio: float
    pds_percentage: float

@app.post("/api/v1/pcf/calculate")
def calculate_pcf(data: EmissionsData):
    """
    [Internal] PTA (PCF Translator Agent) Logic
    Calculates PCF based on CBAM & PACT/WBCSD standards.
    """
    # 1. Scope 1 (Direct Emissions) - Fuel * Emission Factor
    emission_factor_fuel = 2.5
    scope_1 = data.fuel_usage_kg * emission_factor_fuel
    
    # 2. Scope 2 (Indirect Emissions) - Electricity * Grid Emission Factor
    emission_factor_grid = 0.45
    scope_2 = data.electricity_kwh * emission_factor_grid
    
    # 3. Scope 3 (Precursors) - CBAM specific
    scope_3 = data.precursors_emissions_kg
    
    # Total before allocation
    total_emissions = scope_1 + scope_2 + scope_3
    
    # 4. Co-product Allocation (Mass & Economic Value)
    allocation_deduction = total_emissions * data.coproduct_ratio
    allocated_emissions = total_emissions - allocation_deduction
    
    # 5. Final PCF (Product Carbon Footprint) per kg of product
    pcf_per_kg = allocated_emissions / data.production_kg
    
    # Save the latest calculated data (Aggregated / Masked for EDC)
    global latest_pcf_data
    latest_pcf_data = {
        "timestamp": time.time(),
        "asset_id": f"urn:uuid:posco-asset-{data.equipment_id}",
        "pcf_value": round(pcf_per_kg, 4),
        "unit": "kg CO2e / kg",
        "pds": data.pds_percentage,
        "standards": ["CX-0136", "EU-CBAM-2026"],
        "masked": True # Indicates trade secrets (temperatures, recipes) are stripped
    }
    
    return {"status": "success", "calculated_pcf": latest_pcf_data}

@app.get("/api/v1/aas/submodels/pcf")
def get_aas_pcf():
    """
    [External] ECA (EDC Connector Agent) Logic
    Returns masked AAS Submodel for external Catena-X data exchange.
    """
    if not latest_pcf_data:
        # Return a mock default if no calculation has been run yet
        return {
            "submodelElements": [
                {"idShort": "productCarbonFootprint", "value": "1.852", "unit": "kg CO2e / kg"},
                {"idShort": "primaryDataShare", "value": "85.0", "unit": "%"}
            ],
            "masked": True
        }
        
    return {
        "submodelElements": [
            {"idShort": "assetId", "value": latest_pcf_data["asset_id"]},
            {"idShort": "productCarbonFootprint", "value": str(latest_pcf_data["pcf_value"]), "unit": latest_pcf_data["unit"]},
            {"idShort": "primaryDataShare", "value": str(latest_pcf_data["pds"]), "unit": "%"},
            {"idShort": "standards", "value": ",".join(latest_pcf_data["standards"])}
        ],
        "metadata": {
            "masked": latest_pcf_data["masked"],
            "timestamp": latest_pcf_data["timestamp"]
        }
    }

@app.get("/")
def read_root():
    return FileResponse("dashboard.html")

@app.get("/dashboard.html")
def read_dashboard():
    return FileResponse("dashboard.html")

if __name__ == "__main__":
    import uvicorn
    # Run server locally: uvicorn mockup_server:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
