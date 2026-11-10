#pragma once
#include <cmath>
#include <stdexcept>
namespace mirage::profile
{
// All measurements use centimetres; absent measurements are represented by std::nullopt.
struct BodyMeasurements
{
    double height, shoulderWidth, chest, waist, hip;
    void validate() const
    {
        for (double value : {height, shoulderWidth, chest, waist, hip})
            if (!std::isfinite(value) || value <= 0 || value > 1000)
                throw std::invalid_argument("measurements_must_be_positive_centimetres_up_to_1000");
    }
};
} // namespace mirage::profile
