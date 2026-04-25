<?php

namespace App\Enums;

enum ReadingType: string
{
    case Electricity = 'electricity';
    case Water = 'water';
    case Gas = 'gas';
}
