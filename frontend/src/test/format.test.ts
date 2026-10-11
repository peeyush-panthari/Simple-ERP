/**
 * Parity tests: every expectation in golden.json was produced by running the
 * Reflex app's own Python (format.py, and the status helpers in ui_kit.py) on
 * the same inputs - including the round-half-even ties (2.5, 12.25, 0.125 ...)
 * where Python and JavaScript rounding disagree.
 */
import { describe, expect, it } from "vitest";
import * as format from "@/lib/format";
import { bucketLabel, humanise, rawItemStatusLabel, toneFor } from "@/lib/status";
import golden from "./golden.json";

type Case = [unknown, string, string?];
const cases = golden as unknown as Record<string, Case[]>;

describe("format.ts matches format.py", () => {
  it.each(cases.money)("money(%j) -> %s", (input, expected, currency) => {
    expect(format.money(input as never, currency ?? "INR")).toBe(expected);
  });
  it.each(cases.compactMoney)("compactMoney(%j) -> %s", (input, expected) => {
    expect(format.compactMoney(input as never)).toBe(expected);
  });
  it.each(cases.qty)("qty(%j) -> %s", (input, expected, uom) => {
    expect(format.qty(input as never, uom)).toBe(expected);
  });
  it.each(cases.percent)("percent(%j) -> %s", (input, expected) => {
    expect(format.percent(input as never)).toBe(expected);
  });
  it.each(cases.date)("date(%j) -> %s", (input, expected) => {
    expect(format.date(input as never)).toBe(expected);
  });
  it.each(cases.dateTime)("dateTime(%j) -> %s", (input, expected) => {
    expect(format.dateTime(input as never)).toBe(expected);
  });
  it.each(cases.timeOnly)("timeOnly(%j) -> %s", (input, expected) => {
    expect(format.timeOnly(input as never)).toBe(expected);
  });
});

describe("status vocabulary matches ui_kit.py", () => {
  it.each(cases.toneFor)("toneFor(%j) -> %s", (input, expected) => expect(toneFor(input as string)).toBe(expected));
  it.each(cases.humanise)("humanise(%j) -> %s", (input, expected) => expect(humanise(input as string)).toBe(expected));
  it.each(cases.bucketLabel)("bucketLabel(%j) -> %s", (input, expected) => expect(bucketLabel(input as string)).toBe(expected));
  it.each(cases.rawItemStatusLabel)("rawItemStatusLabel(%j) -> %s", (input, expected) => expect(rawItemStatusLabel(input as never)).toBe(expected));
});

describe("pyRound", () => {
  it("rounds ties to even like Python", () => {
    expect([0.5, 1.5, 2.5, 3.5, -2.5].map((x) => format.pyRound(x))).toEqual([0, 2, 2, 4, -2]);
    expect(format.pyRound(0.125, 2)).toBe(0.12);
    expect(format.pyRound(2.675, 2)).toBe(2.67); // binary repr is just below the tie
  });
});
