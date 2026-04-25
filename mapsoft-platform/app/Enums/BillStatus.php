<?php

namespace App\Enums;

enum BillStatus: string
{
    case Pending = 'pending';
    case Paid = 'paid';
    case Overdue = 'overdue';
}
