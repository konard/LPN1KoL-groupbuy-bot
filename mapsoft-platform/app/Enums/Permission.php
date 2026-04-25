<?php

namespace App\Enums;

enum Permission: string
{
    case ViewUsers = 'view_users';
    case CreateUsers = 'create_users';
    case EditUsers = 'edit_users';
    case DeleteUsers = 'delete_users';
    case ViewReadings = 'view_readings';
    case ManageTariffs = 'manage_tariffs';
    case ManageBills = 'manage_bills';
    case ExportData = 'export_data';
}
