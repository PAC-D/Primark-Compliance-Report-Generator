import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn's class merger: conditional classes, later Tailwind classes win. */
export const cn = (...inputs: ClassValue[]): string => twMerge(clsx(inputs));
