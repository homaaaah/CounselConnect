export const STANDARD_CONCERNS = [
  { value: "FAMILY_PROBLEM", label: "Family problem" },
  { value: "FINANCIAL_PROBLEM", label: "Financial problem" },
  { value: "ACADEMIC_PROBLEM", label: "Academic problem" },
  { value: "RELATIONSHIP_PROBLEM", label: "Relationship problem" },
];

export const CUSTOM_CONCERN = { value: "CUSTOM", label: "Custom" };
export const ALL_CONCERNS_VALUE = "ALL_OF_THE_ABOVE";

const LABEL_BY_VALUE = new Map([
  ...STANDARD_CONCERNS,
  CUSTOM_CONCERN,
].map(option => [option.value, option.label]));

export function concernLabel(value) {
  return LABEL_BY_VALUE.get(value) ?? value;
}

export function toggleConcernCategory(selected, value) {
  if (value === ALL_CONCERNS_VALUE) {
    const allSelected = STANDARD_CONCERNS.every(option => selected.includes(option.value));
    return allSelected
      ? selected.filter(item => !STANDARD_CONCERNS.some(option => option.value === item))
      : [...selected, ...STANDARD_CONCERNS.map(option => option.value).filter(item => !selected.includes(item))];
  }
  return selected.includes(value)
    ? selected.filter(item => item !== value)
    : [...selected, value];
}
