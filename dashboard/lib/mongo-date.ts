/**
 * MongoDB aggregation expression that converts a value to a Date, handling
 * mixed legacy formats: BSON Date, ISO string, unix-seconds number, or
 * unix-milliseconds number. Returns null for missing/incompatible values.
 *
 * Detection rule: numeric values < 1e12 are treated as unix-seconds
 * (since 1e12 ms ≈ year 2001 and 1e12 sec ≈ year 33658). String values
 * use $toDate's built-in ISO 8601 parser.
 */
export const coerceDateExpr = (fieldRef: Record<string, unknown>): Record<string, unknown> => {
  const isNumeric = { $in: [{ $type: fieldRef }, ['double', 'int', 'long', 'decimal']] };
  const isString = { $eq: [{ $type: fieldRef }, 'string'] };
  const isDate = { $eq: [{ $type: fieldRef }, 'date'] };

  return {
    $switch: {
      branches: [
        { case: isDate, then: fieldRef },
        { case: isString, then: { $toDate: fieldRef } },
        {
          case: {
            $and: [
              isNumeric,
              { $lt: [fieldRef, 1_000_000_000_000] },
            ],
          },
          then: { $toDate: { $multiply: [fieldRef, 1000] } },
        },
        {
          case: isNumeric,
          then: { $toDate: fieldRef },
        },
      ],
      default: null,
    },
  };
};
