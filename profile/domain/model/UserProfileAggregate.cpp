#include "UserProfileAggregate.h"
#include <ctime>
#include <regex>
namespace mirage::profile
{
namespace
{
bool uuid(const std::string &value)
{
    static const std::regex format("^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$");
    return std::regex_match(value, format);
}
void validateDate(const std::string &value)
{
    static const std::regex format("^[0-9]{4}-[0-9]{2}-[0-9]{2}$");
    if (!std::regex_match(value, format))
        throw std::invalid_argument("invalid_birth_date");
    int year = std::stoi(value.substr(0, 4)), month = std::stoi(value.substr(5, 2)),
        day = std::stoi(value.substr(8, 2));
    const int days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    bool leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    if (year < 1900 || month < 1 || month > 12 || day < 1 ||
        day > days[month - 1] + (month == 2 && leap))
        throw std::invalid_argument("invalid_birth_date");
    auto now = std::time(nullptr);
    std::tm current{};
#ifdef _WIN32
    gmtime_s(&current, &now);
#else
    gmtime_r(&now, &current);
#endif
    int today = (current.tm_year + 1900) * 10000 + (current.tm_mon + 1) * 100 + current.tm_mday;
    if (year * 10000 + month * 100 + day > today)
        throw std::invalid_argument("birth_date_in_future");
}
} // namespace
UserProfileAggregate::UserProfileAggregate(UserProfile profile, StylePreferences preferences,
                                           std::optional<BodyMeasurements> measurements)
    : profile_(std::move(profile))
{
    if (!uuid(profile_.id) || !uuid(profile_.userId))
        throw std::invalid_argument("invalid_profile_identity");
    updateProfile(profile_.displayName, profile_.birthDate, profile_.profileImageUrl);
    updatePreferences(std::move(preferences));
    if (measurements)
        registerMeasurements(*measurements);
}
void UserProfileAggregate::updateProfile(std::string name, std::optional<std::string> birthDate,
                                         std::optional<std::string> imageUrl)
{
    if (name.empty() || name.size() > 100 ||
        name.find_first_not_of(" \r\n\t") == std::string::npos ||
        name.find('\0') != std::string::npos)
        throw std::invalid_argument("invalid_display_name");
    if (birthDate)
        validateDate(*birthDate);
    if (imageUrl &&
        (imageUrl->size() > 2048 || imageUrl->compare(0, 8, "https://") != 0 ||
         imageUrl->size() <= 8 || imageUrl->find_first_of(" \r\n\t") != std::string::npos))
        throw std::invalid_argument("profile_image_requires_https");
    profile_.displayName = std::move(name);
    profile_.birthDate = std::move(birthDate);
    profile_.profileImageUrl = std::move(imageUrl);
}
void UserProfileAggregate::updatePreferences(StylePreferences preferences)
{
    preferences.validate();
    preferences_ = std::move(preferences);
}
void UserProfileAggregate::registerMeasurements(BodyMeasurements measurements)
{
    measurements.validate();
    measurements_ = measurements;
}
} // namespace mirage::profile
