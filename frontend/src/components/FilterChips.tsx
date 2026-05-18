import type { ParsedQuery } from "@/lib/types";
import { BedIcon, PawIcon, PinIcon, SparkIcon } from "./Icon";
import { Pill } from "./Pill";

const fmtMoney = (n: number) => "$" + n.toLocaleString();

export function FilterChips({ parsed }: { parsed: ParsedQuery }) {
  const chips: React.ReactNode[] = [];

  if (parsed.city || parsed.province) {
    chips.push(
      <Pill key="loc" variant="brand" icon={<PinIcon size={12} />}>
        {[parsed.city, parsed.province].filter(Boolean).join(", ")}
      </Pill>,
    );
  }
  if (parsed.max_rent != null) {
    chips.push(
      <Pill key="rent" variant="info">≤ {fmtMoney(parsed.max_rent)}/mo</Pill>,
    );
  }
  if (parsed.min_rent != null) {
    chips.push(
      <Pill key="minrent" variant="info">≥ {fmtMoney(parsed.min_rent)}/mo</Pill>,
    );
  }
  if (parsed.min_bedrooms != null) {
    chips.push(
      <Pill key="bd" icon={<BedIcon size={12} />}>
        {parsed.min_bedrooms === 0.5 ? "Studio+" : `${parsed.min_bedrooms}+ bd`}
      </Pill>,
    );
  }
  if (parsed.min_bathrooms != null) {
    chips.push(<Pill key="ba">{parsed.min_bathrooms}+ ba</Pill>);
  }
  if (parsed.property_types.length) {
    chips.push(
      <Pill key="pt" variant="outline">{parsed.property_types.join(" · ")}</Pill>,
    );
  }
  if (parsed.furnished === true) chips.push(<Pill key="furn" variant="warm">Furnished</Pill>);
  if (parsed.pet_friendly === true) {
    chips.push(
      <Pill key="pet" variant="brand" icon={<PawIcon size={12} />}>Pet-friendly</Pill>,
    );
  }
  for (const u of parsed.utilities_required) {
    chips.push(<Pill key={`u-${u}`} variant="info">incl. {u}</Pill>);
  }
  if (parsed.lease_length_months_max != null) {
    chips.push(
      <Pill key="lease" variant="outline">≤ {parsed.lease_length_months_max} mo lease</Pill>,
    );
  }
  if (parsed.commute_target) {
    chips.push(
      <Pill key="commute" variant="outline">
        commute → {parsed.commute_target}
        {parsed.commute_max_km != null ? ` (${parsed.commute_max_km}km)` : ""}
      </Pill>,
    );
  }
  if (parsed.lifestyle_query) {
    chips.push(
      <Pill key="vibe" variant="default" icon={<SparkIcon size={12} />}>
        “{parsed.lifestyle_query}”
      </Pill>,
    );
  }

  if (chips.length === 0) return null;
  return <div className="flex flex-wrap gap-1.5">{chips}</div>;
}
