"use client";

import { signOf } from "@/lib/format";
import NumberFlow, { continuous, NumberFlowGroup, useCanAnimate, type Format } from "@number-flow/react";

export { NumberFlowGroup }; // wrap a value and its change so they roll together

// Carton Connect's change timing (150–250 ms)
const spin = { duration: 250, easing: "cubic-bezier(.2, 0, 0, 1)" };
const fade = { duration: 200, easing: "ease-out" };
const PLUGINS = [continuous];

/** A number that rolls to its new value when it changes; static under reduced motion. null shows "–". */
export function Num({ value, format, suffix, signed }: {
  value: number | null;
  format?: Intl.NumberFormatOptions;
  suffix?: string;
  signed?: boolean;
}) {
  const animated = useCanAnimate({ respectMotionPreference: true });
  if (value === null || !Number.isFinite(value)) return <span>–</span>;
  return (
    <NumberFlow
      value={signed ? Math.abs(value) : value}
      locales="en-GB"
      format={format as Format} // NumberFlow takes all but scientific and engineering notation
      prefix={signed ? signOf(value, format?.maximumFractionDigits) : undefined} // NumberFlow has no U+2212: draw the sign ourselves
      suffix={suffix}
      animated={animated}
      plugins={PLUGINS}
      transformTiming={spin}
      spinTiming={spin}
      opacityTiming={fade}
    />
  );
}
