import { Badge } from "@/components/ui/badge";
import { Tip } from "@/components/tss/tip";

export function SymbolLabel({
  symbol,
  zeroFee,
  context,
  hideQuote = false,
}: {
  symbol: string;
  zeroFee?: boolean | null;
  context?: boolean;
  hideQuote?: boolean;
}) {
  const [base, quote] = symbol.split("_");
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span className="font-semibold">{base}</span>
      {hideQuote ? null : <span className="text-[11px] text-muted-foreground">{quote ?? ""}</span>}
      {context ? (
        <Badge variant="outline" className="h-4 px-1.5 text-[10px] text-muted-foreground">
          context
        </Badge>
      ) : null}
      {zeroFee ? (
        <Tip content="MEXC reports both maker and taker fee = 0 (display only)" focusable>
          <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
            0 fee
          </Badge>
        </Tip>
      ) : null}
    </span>
  );
}
