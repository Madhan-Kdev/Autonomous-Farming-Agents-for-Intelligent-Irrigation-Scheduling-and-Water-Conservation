import type { Farm } from '../types';
import { MapPin } from 'lucide-react';

interface Props {
  farms: Farm[];
  selectedFarmId: number;
  onSelectFarm: (farmId: number) => void;
  selectedFieldId: number | null;
  onSelectField: (fieldId: number | null) => void;
  selectedZoneId: number | null;
  onSelectZone: (zoneId: number | null) => void;
}

export const FarmContextSection: React.FC<Props> = ({
  farms,
  selectedFarmId,
  onSelectFarm,
  selectedFieldId,
  onSelectField,
  selectedZoneId,
  onSelectZone,
}) => {
  const currentFarm = farms.find((f) => f.id === selectedFarmId) || farms[0];
  const fields = currentFarm?.fields || [];
  const currentField = fields.find((f) => f.id === selectedFieldId);
  const zones = currentField ? currentField.zones : fields.flatMap((f) => f.zones);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-sky-500/10 text-sky-400 rounded-lg">
          <MapPin className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Farm, Field & Zone Targeting</h3>
          <p className="text-xs text-slate-400">
            Targeting context for spatial allocation and hydraulic network configuration.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Farm Select */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Agricultural Facility / Farm
          </label>
          <select
            value={selectedFarmId}
            onChange={(e) => {
              const fid = Number(e.target.value);
              onSelectFarm(fid);
              onSelectField(null);
              onSelectZone(null);
            }}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            {farms.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.total_area_ha ?? '—'} ha)
              </option>
            ))}
          </select>
          {currentFarm && (
            <div className="mt-1 text-[11px] text-slate-400 flex items-center gap-2">
              <span>Lat: {currentFarm.latitude.toFixed(4)}°</span>
              <span>Lon: {currentFarm.longitude.toFixed(4)}°</span>
            </div>
          )}
        </div>

        {/* Field Select */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Target Field (Optional)
          </label>
          <select
            value={selectedFieldId ?? ''}
            onChange={(e) => {
              const val = e.target.value ? Number(e.target.value) : null;
              onSelectField(val);
              onSelectZone(null);
            }}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            <option value="">-- All Fields in Farm --</option>
            {fields.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.area_ha} ha) - {f.soil_type || 'Default Soil'}
              </option>
            ))}
          </select>
          <div className="mt-1 text-[11px] text-slate-400">
            {currentField ? `${currentField.zones.length} zone(s) identified` : 'Farm-wide aggregation'}
          </div>
        </div>

        {/* Zone Select */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Specific Management Zone
          </label>
          <select
            value={selectedZoneId ?? ''}
            onChange={(e) => {
              const val = e.target.value ? Number(e.target.value) : null;
              onSelectZone(val);
            }}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            <option value="">-- All Active Zones in Farm/Field --</option>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name} ({z.crop_name || 'Crop'} - {z.area_ha} ha, {z.irrigation_method || 'Drip'})
              </option>
            ))}
          </select>
          <div className="mt-1 text-[11px] text-slate-400">
            {selectedZoneId
              ? `Focused single-zone precision scheduling`
              : `Multi-zone prioritized allocation`}
          </div>
        </div>
      </div>
    </div>
  );
};
