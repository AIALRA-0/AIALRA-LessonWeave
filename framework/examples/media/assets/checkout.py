from dataclasses import dataclass


@dataclass(frozen=True)
class OrderLine:
    name: str
    unit_price: int
    quantity: int

    def subtotal(self) -> int:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class DiscountPolicy:
    threshold: int
    reduction: int

    def apply(self, total: int) -> int:
        if total >= self.threshold:
            return total - self.reduction
        return total


def checkout(lines: list[OrderLine], policy: DiscountPolicy) -> dict[str, int]:
    original_total = sum(line.subtotal() for line in lines)
    payable = policy.apply(original_total)
    return {"original_total": original_total, "discount": original_total - payable, "payable": payable}


if __name__ == "__main__":
    lines = [OrderLine("notebook", 12, 3), OrderLine("pen", 4, 2)]
    policy = DiscountPolicy(threshold=40, reduction=5)
    result = checkout(lines, policy)
    print(result)
