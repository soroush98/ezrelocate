// Tiny inline SVG icon set — no extra dep, no runtime cost.
// Each accepts standard SVG props (size, strokeWidth, etc.) via className.

type IconProps = React.SVGProps<SVGSVGElement> & { size?: number };

const base = (props: IconProps): React.SVGProps<SVGSVGElement> => ({
  width: props.size ?? 16,
  height: props.size ?? 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  ...props,
});

export const PinIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 21s-7-7.06-7-12a7 7 0 1 1 14 0c0 4.94-7 12-7 12Z" />
    <circle cx="12" cy="9" r="2.5" />
  </svg>
);

export const BedIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3 18V8" />
    <path d="M21 18v-5a3 3 0 0 0-3-3H8a3 3 0 0 0-3 3" />
    <circle cx="7.5" cy="12.5" r="1.5" />
    <path d="M3 18h18" />
  </svg>
);

export const BathIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 12V6a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2" />
    <path d="M3 12h18v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3Z" />
    <path d="M7 19l-1 2M17 19l1 2" />
  </svg>
);

export const RulerIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3 17 17 3l4 4L7 21 3 17Z" />
    <path d="M7 13l1.5 1.5M9.5 10.5l1.5 1.5M12 8l1.5 1.5M14.5 5.5l1.5 1.5" />
  </svg>
);

export const PawIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="6" cy="11" r="1.6" />
    <circle cx="10" cy="6" r="1.6" />
    <circle cx="14" cy="6" r="1.6" />
    <circle cx="18" cy="11" r="1.6" />
    <path d="M8 16c0-2.5 2-4 4-4s4 1.5 4 4-2 4-4 4-4-1.5-4-4Z" />
  </svg>
);

export const SparkIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
  </svg>
);

export const ArrowRightIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const ExternalIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M14 4h6v6" />
    <path d="M20 4 10 14" />
    <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
  </svg>
);

export const FlameIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3s4 4 4 8a4 4 0 1 1-8 0c0-1 1-2 2-2-1-2 2-6 2-6Z" />
  </svg>
);

export const SearchIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);
