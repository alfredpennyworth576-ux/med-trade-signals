"""
Paper trading simulation for signal testing
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
from pathlib import Path
import sys
sys.path.insert(0, str(__file__).replace('output/paper_trading.py', ''))
from utils.config import config
from utils.logger import setup_logger

logger = setup_logger("paper_trading")


@dataclass
class TradeRecord:
    """Record of a paper trade"""
    trade_id: str
    signal_id: str
    ticker: str
    signal_type: str
    action: str  # BUY or SELL
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: int = 100  # Default to 100 shares for paper trading
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    entry_at: Optional[str] = None
    exit_at: Optional[str] = None
    status: str = "OPEN"  # OPEN or CLOSED
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def calculate_pnl(self) -> Tuple[float, float]:
        """
        Calculate P&L for this trade
        
        Returns:
        - Tuple of (pnl_amount, pnl_percent)
        """
        if self.entry_price is None or self.exit_price is None:
            return 0.0, 0.0
        
        pnl = (self.exit_price - self.entry_price) * self.quantity
        pnl_percent = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        
        self.pnl = round(pnl, 2)
        self.pnl_percent = round(pnl_percent, 2)
        
        return self.pnl, self.pnl_percent


@dataclass
class Position:
    """Current position in a ticker"""
    ticker: str
    quantity: int
    average_cost: float
    total_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_percent: Optional[float] = None
    
    def update_market_value(self, current_price: float):
        """Update position based on current market price"""
        self.current_price = current_price
        self.market_value = self.quantity * current_price
        self.unrealized_pnl = (current_price - self.average_cost) * self.quantity
        self.unrealized_pnl_percent = ((current_price - self.average_cost) / self.average_cost) * 100
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PaperTrader:
    """Paper trading simulator for testing signals"""
    
    def __init__(self, initial_cash: float = 100000.0):
        """
        Initialize paper trader
        
        Parameters:
        - initial_cash: Starting cash balance (default: $100,000)
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.closed_trades: List[TradeRecord] = []
        
        # Create data directory
        self.data_dir = Path(config.SIGNALS_DIR) / "paper_trading"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized PaperTrader with ${initial_cash:,.2f}")
    
    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value (cash + positions)"""
        total = self.cash
        for position in self.positions.values():
            if position.market_value:
                total += position.market_value
        return round(total, 2)
    
    def get_portfolio_pnl(self) -> Tuple[float, float]:
        """
        Calculate total portfolio P&L
        
        Returns:
        - Tuple of (pnl_amount, pnl_percent)
        """
        portfolio_value = self.get_portfolio_value()
        pnl = portfolio_value - self.initial_cash
        pnl_percent = (pnl / self.initial_cash) * 100
        
        return round(pnl, 2), round(pnl_percent, 2)
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """Get current position for a ticker"""
        return self.positions.get(ticker.upper())
    
    def execute_signal(self, signal: Dict, entry_price: Optional[float] = None) -> TradeRecord:
        """
        Execute a trading signal (open a position)
        
        Parameters:
        - signal: Signal dictionary (from TradingSignal.to_dict())
        - entry_price: Entry price (optional, will use target estimate if not provided)
        
        Returns:
        - TradeRecord for the executed trade
        """
        ticker = signal.get('ticker', 'UNKNOWN').upper()
        sentiment = signal.get('sentiment', 'neutral').lower()
        
        # Determine action based on sentiment
        if sentiment == 'positive':
            action = 'BUY'
        elif sentiment == 'negative':
            action = 'SELL'
        else:
            logger.warning(f"Neutral sentiment for signal {signal.get('signal_id')}, skipping execution")
            return TradeRecord(
                trade_id=f"skip_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                signal_id=signal.get('signal_id', ''),
                ticker=ticker,
                signal_type=signal.get('signal_type', 'UNKNOWN'),
                action='SKIP',
                status='SKIPPED'
            )
        
        # Check if we already have a position
        existing_position = self.get_position(ticker)
        
        if existing_position and action == 'BUY':
            logger.warning(f"Already have position in {ticker}, skipping BUY signal")
            return TradeRecord(
                trade_id=f"skip_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                signal_id=signal.get('signal_id', ''),
                ticker=ticker,
                signal_type=signal.get('signal_type', 'UNKNOWN'),
                action='SKIP',
                status='SKIPPED',
                notes=f"Already hold {existing_position.quantity} shares"
            )
        
        if not existing_position and action == 'SELL':
            logger.warning(f"No position in {ticker}, skipping SELL signal")
            return TradeRecord(
                trade_id=f"skip_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                signal_id=signal.get('signal_id', ''),
                ticker=ticker,
                signal_type=signal.get('signal_type', 'UNKNOWN'),
                action='SKIP',
                status='SKIPPED',
                notes="No existing position to sell"
            )
        
        # Use provided price or estimate based on target
        if entry_price is None:
            # Estimate price (simplified - in real app would fetch from API)
            target_upside = signal.get('target_upside', 0)
            entry_price = 100.0  # Default base price for paper trading
            if target_upside > 0:
                # Assume current price is near target downside
                entry_price = 100.0 / (1 + abs(target_upside) / 100)
            else:
                entry_price = 100.0
        
        trade_id = f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{ticker}"
        
        # Create trade record
        if action == 'BUY':
            # Calculate quantity (use 10% of cash per trade)
            max_investment = self.cash * 0.10
            quantity = int(max_investment // entry_price)
            quantity = max(100, min(quantity, 1000))  # Between 100 and 1000 shares
            
            total_cost = quantity * entry_price
            
            if total_cost > self.cash:
                logger.warning(f"Insufficient cash for {ticker} trade")
                return TradeRecord(
                    trade_id=trade_id,
                    signal_id=signal.get('signal_id', ''),
                    ticker=ticker,
                    signal_type=signal.get('signal_type', 'UNKNOWN'),
                    action='SKIP',
                    status='SKIPPED',
                    notes="Insufficient cash"
                )
            
            # Deduct cash
            self.cash -= total_cost
            
            # Update or create position
            if existing_position:
                # Average down/up
                old_total = existing_position.quantity * existing_position.average_cost
                new_total = quantity * entry_price
                new_quantity = existing_position.quantity + quantity
                new_avg_cost = (old_total + new_total) / new_quantity
                
                existing_position.quantity = new_quantity
                existing_position.average_cost = round(new_avg_cost, 2)
                existing_position.total_cost = existing_position.quantity * existing_position.average_cost
            else:
                # New position
                self.positions[ticker] = Position(
                    ticker=ticker,
                    quantity=quantity,
                    average_cost=round(entry_price, 2),
                    total_cost=round(total_cost, 2)
                )
            
            trade = TradeRecord(
                trade_id=trade_id,
                signal_id=signal.get('signal_id', ''),
                ticker=ticker,
                signal_type=signal.get('signal_type', 'UNKNOWN'),
                action='BUY',
                entry_price=round(entry_price, 2),
                quantity=quantity,
                entry_at=datetime.now().isoformat(),
                status='OPEN'
            )
        
        else:  # SELL
            # Sell entire position
            quantity = existing_position.quantity
            total_proceeds = quantity * entry_price
            
            # Add cash
            self.cash += total_proceeds
            
            # Close position
            del self.positions[ticker]
            
            trade = TradeRecord(
                trade_id=trade_id,
                signal_id=signal.get('signal_id', ''),
                ticker=ticker,
                signal_type=signal.get('signal_type', 'UNKNOWN'),
                action='SELL',
                entry_price=existing_position.average_cost,
                exit_price=round(entry_price, 2),
                quantity=quantity,
                entry_at=datetime.now().isoformat(),  # Would be real entry date in production
                exit_at=datetime.now().isoformat(),
                status='CLOSED'
            )
            
            # Calculate P&L
            trade.calculate_pnl()
            self.closed_trades.append(trade)
        
        self.trades.append(trade)
        logger.info(f"Executed {action} {quantity} {ticker} @ ${entry_price:.2f}")
        
        return trade
    
    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions
        
        Parameters:
        - prices: Dictionary of {ticker: current_price}
        """
        for ticker, price in prices.items():
            position = self.get_position(ticker)
            if position:
                position.update_market_value(price)
                logger.debug(f"Updated {ticker} price to ${price:.2f}")
    
    def close_position(self, ticker: str, exit_price: float) -> Optional[TradeRecord]:
        """
        Close a position at a specific price
        
        Parameters:
        - ticker: Ticker symbol
        - exit_price: Exit price
        
        Returns:
        - TradeRecord for the closed position, or None if no position exists
        """
        position = self.get_position(ticker)
        if not position:
            logger.warning(f"No position in {ticker} to close")
            return None
        
        # Calculate proceeds
        proceeds = position.quantity * exit_price
        self.cash += proceeds
        
        # Find and close the trade
        for trade in self.trades:
            if trade.ticker == ticker and trade.status == 'OPEN' and trade.action == 'BUY':
                trade.exit_price = round(exit_price, 2)
                trade.exit_at = datetime.now().isoformat()
                trade.status = 'CLOSED'
                trade.calculate_pnl()
                self.closed_trades.append(trade)
                break
        
        # Remove position
        del self.positions[ticker]
        
        logger.info(f"Closed {ticker} position @ ${exit_price:.2f}")
        
        return trade if trade else None
    
    def get_summary(self) -> Dict:
        """Get portfolio summary"""
        portfolio_value = self.get_portfolio_value()
        pnl, pnl_percent = self.get_portfolio_pnl()
        
        # Position summary
        positions_summary = []
        for position in self.positions.values():
            positions_summary.append({
                "ticker": position.ticker,
                "quantity": position.quantity,
                "avg_cost": position.average_cost,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pnl,
                "unrealized_pnl_percent": position.unrealized_pnl_percent
            })
        
        # Trade statistics
        closed_count = len(self.closed_trades)
        if closed_count > 0:
            total_trades_pnl = sum(t.pnl or 0 for t in self.closed_trades)
            winning_trades = sum(1 for t in self.closed_trades if t.pnl and t.pnl > 0)
            losing_trades = sum(1 for t in self.closed_trades if t.pnl and t.pnl < 0)
            win_rate = (winning_trades / closed_count) * 100
        else:
            total_trades_pnl = 0
            winning_trades = 0
            losing_trades = 0
            win_rate = 0
        
        return {
            "cash": round(self.cash, 2),
            "portfolio_value": portfolio_value,
            "initial_cash": self.initial_cash,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "positions": positions_summary,
            "open_positions": len(self.positions),
            "total_trades": len(self.trades),
            "closed_trades": closed_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_trades_pnl": round(total_trades_pnl, 2)
        }
    
    def save_state(self, filename: Optional[str] = None):
        """Save trader state to file"""
        if filename is None:
            filename = self.data_dir / f"trader_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        state = {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "positions": [p.to_dict() for p in self.positions.values()],
            "trades": [t.to_dict() for t in self.trades],
            "saved_at": datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Saved trader state to {filename}")
    
    def load_state(self, filename: str):
        """Load trader state from file"""
        with open(filename, 'r') as f:
            state = json.load(f)
        
        self.initial_cash = state['initial_cash']
        self.cash = state['cash']
        
        self.positions = {}
        for pos_data in state['positions']:
            position = Position(**pos_data)
            self.positions[position.ticker] = position
        
        self.trades = [TradeRecord(**t) for t in state['trades']]
        self.closed_trades = [t for t in self.trades if t.status == 'CLOSED']
        
        logger.info(f"Loaded trader state from {filename}")


if __name__ == "__main__":
    # Test the paper trader
    trader = PaperTrader(initial_cash=100000.0)
    
    # Test signal
    test_signal = {
        "signal_id": "test_123",
        "signal_type": "FDA_APPROVAL",
        "ticker": "PFE",
        "headline": "FDA approves new treatment",
        "confidence": 90,
        "sentiment": "positive",
        "target_upside": 15.0,
        "target_downside": -5.0,
        "created_at": datetime.now().isoformat()
    }
    
    # Execute signal
    trade = trader.execute_signal(test_signal)
    print(f"\nExecuted trade: {trade.trade_id}")
    print(f"Action: {trade.action} {trade.quantity} {trade.ticker} @ ${trade.entry_price}")
    
    # Update price
    trader.update_prices({"PFE": 108.0})
    
    # Get summary
    summary = trader.get_summary()
    print(f"\nPortfolio Summary:")
    print(f"  Cash: ${summary['cash']:,.2f}")
    print(f"  Portfolio Value: ${summary['portfolio_value']:,.2f}")
    print(f"  P&L: ${summary['pnl']:,.2f} ({summary['pnl_percent']:.2f}%)")
    
    # Close position
    trader.close_position("PFE", 110.0)
    
    # Final summary
    summary = trader.get_summary()
    print(f"\nFinal P&L: ${summary['pnl']:,.2f} ({summary['pnl_percent']:.2f}%)")
    print(f"Win Rate: {summary['win_rate']:.1f}%")
