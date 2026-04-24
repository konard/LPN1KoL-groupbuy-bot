<?php

namespace App\Enums;

enum NotificationType: string
{
    case BillNew = 'bill_new';
    case BillOverdue = 'bill_overdue';
    case TariffChanged = 'tariff_changed';
}
