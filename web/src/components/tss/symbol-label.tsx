import { Badge } from "@/components/ui/badge";
import { Tip } from "@/components/tss/tip";

/**
 * MEXC USDT perpetual on TradingView, e.g. BTC_USDT -> MEXC:BTCUSDT.P.
 * MEXC names tokenized stocks BASESTOCK_USDT, TradingView lists them as BASEUSDT.P
 * (observed for MRVL; not verified for every STOCK contract).
 */
function tradingViewUrl(symbol: string): string {
  const [base = "", quote = ""] = symbol.split("_");
  const tvBase = base.length > 5 && base.endsWith("STOCK") ? base.slice(0, -5) : base;
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(`MEXC:${tvBase}${quote}.P`)}`;
}

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
      <Tip content="Open in TradingView (MEXC perp)">
        <a
          href={tradingViewUrl(symbol)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="rounded-sm font-semibold hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {base}
        </a>
      </Tip>
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
